"""
Pre-Trade Audit Module - Adversarial Intelligence Layer

Reliability Level: L6 Critical
Input Constraints: All signals must have valid correlation_id
Side Effects: Invokes Ollama DeepSeek-R1, writes to audit logs

This module implements adversarial reasoning using DeepSeek-R1 to validate
trade signals before execution. Every signal must survive 3 logical rejection
attempts before approval.

Python 3.8 Compatible - No union type hints (X | None)
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Awaitable
import asyncio
import time
import re
import logging
from datetime import datetime, timezone

# Configure logging with unique error codes
logger = logging.getLogger("pre_trade_audit")


# =============================================================================
# CONSTANTS
# =============================================================================

# Model configuration
DEEPSEEK_MODEL = "deepseek-r1:8b"
AUDIT_TIMEOUT_SECONDS = 30
CONFIDENCE_THRESHOLD = Decimal("95.00")
REQUIRED_REJECTION_REASONS = 3

# Error codes
ERROR_PRE_AUDIT_TIMEOUT = "PRE_AUDIT_TIMEOUT"
ERROR_MODEL_PARSE_FAIL = "MODEL_PARSE_FAIL"
ERROR_CONFIDENCE_INVALID = "CONFIDENCE_INVALID"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TradeSignal:
    """
    Incoming TradingView webhook signal.
    
    Reliability Level: L6 Critical
    Input Constraints: correlation_id required, price must be Decimal
    Side Effects: None
    """
    correlation_id: str
    symbol: str
    action: str  # "BUY" | "SELL" | "CLOSE"
    price: Decimal
    timestamp_utc: str
    source_ip: Optional[str] = None
    hmac_signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditResult:
    """
    Result of Pre-Trade Audit.
    
    Reliability Level: L6 Critical
    Input Constraints: correlation_id must be valid UUID
    Side Effects: Written to immutable audit table
    """
    correlation_id: str
    confidence_score: Decimal
    rejection_reasons: List[str]
    approved: bool
    audit_timestamp_utc: str
    execution_time_ms: int
    model_used: str
    raw_model_output: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class AuditDecision(Enum):
    """
    Pre-Trade Audit decision outcomes.
    
    Reliability Level: L6 Critical
    """
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


# =============================================================================
# PRE-TRADE AUDIT MODULE
# =============================================================================

class PreTradeAuditModule:
    """
    Adversarial reasoning module using DeepSeek-R1.
    
    Reliability Level: L6 Critical
    Input Constraints: Signal must have valid correlation_id
    Side Effects: Invokes Ollama, writes audit logs
    
    Implements the Cold Path adversarial intelligence as defined in PRD 3.2.
    Every trade signal must survive 3 logical rejection attempts.
    """
    
    def __init__(
        self,
        ollama_callback: Optional[Callable[[str, str], Awaitable[str]]] = None,
        audit_writer: Optional[Callable[[AuditResult], Awaitable[None]]] = None,
        model_name: str = DEEPSEEK_MODEL,
        timeout_seconds: int = AUDIT_TIMEOUT_SECONDS,
        confidence_threshold: Optional[Decimal] = None
    ) -> None:
        """
        Initialize Pre-Trade Audit Module.
        
        Args:
            ollama_callback: Async callback to invoke Ollama (model, prompt) -> response
            audit_writer: Async callback to write audit records
            model_name: Ollama model to use (default: deepseek-r1:8b)
            timeout_seconds: Maximum time for model response (default: 30s)
            confidence_threshold: Minimum confidence for approval (default: 95)
        """
        self._ollama_callback = ollama_callback
        self._audit_writer = audit_writer
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._confidence_threshold = confidence_threshold or CONFIDENCE_THRESHOLD
    
    @property
    def confidence_threshold(self) -> Decimal:
        """Get current confidence threshold."""
        return self._confidence_threshold
    
    def _build_adversarial_prompt(self, signal: TradeSignal) -> str:
        """
        Build the adversarial prompt for DeepSeek-R1.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid TradeSignal required
        Side Effects: None
        
        The prompt instructs the model to act as a skeptical risk analyst
        and generate exactly 3 reasons to REJECT the trade.
        """
        prompt = f"""You are a skeptical risk analyst for a high-stakes trading system.
Your job is to find reasons why a trade should be REJECTED.

TRADE SIGNAL:
- Symbol: {signal.symbol}
- Action: {signal.action}
- Price: {signal.price}
- Timestamp: {signal.timestamp_utc}
- Correlation ID: {signal.correlation_id}

TASK:
Generate EXACTLY 3 logical reasons why this trade should be REJECTED.
Be specific and cite potential risks, market conditions, or technical concerns.

After listing the 3 rejection reasons, provide a CONFIDENCE SCORE from 0-100.
- Score 0-94: Trade should be REJECTED (high risk identified)
- Score 95-100: Trade may proceed (risks are acceptable)

FORMAT YOUR RESPONSE EXACTLY AS:
REJECTION_REASON_1: [Your first reason]
REJECTION_REASON_2: [Your second reason]
REJECTION_REASON_3: [Your third reason]
CONFIDENCE_SCORE: [Number 0-100]

Be thorough and adversarial. The family's capital depends on your analysis."""
        
        return prompt
    
    def parse_rejection_reasons(
        self,
        model_output: str
    ) -> tuple:
        """
        Parse model output into structured rejection reasons and confidence.
        
        Reliability Level: L6 Critical
        Input Constraints: model_output must be non-empty string
        Side Effects: None
        
        Args:
            model_output: Raw text response from DeepSeek-R1
            
        Returns:
            Tuple of (List[str] rejection_reasons, Decimal confidence_score)
            
        Raises:
            ValueError: If parsing fails or confidence is invalid
        """
        if not model_output or not model_output.strip():
            raise ValueError("Empty model output")
        
        rejection_reasons = []  # type: List[str]
        confidence_score = None  # type: Optional[Decimal]
        
        # Parse rejection reasons
        for i in range(1, 4):
            pattern = rf"REJECTION_REASON_{i}:\s*(.+?)(?=REJECTION_REASON_|CONFIDENCE_SCORE:|$)"
            match = re.search(pattern, model_output, re.IGNORECASE | re.DOTALL)
            if match:
                reason = match.group(1).strip()
                # Clean up the reason
                reason = re.sub(r'\s+', ' ', reason)
                if reason:
                    rejection_reasons.append(reason)
        
        # If structured parsing fails, try line-by-line extraction
        if len(rejection_reasons) < REQUIRED_REJECTION_REASONS:
            lines = model_output.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.upper().startswith('CONFIDENCE'):
                    # Check for numbered reasons
                    numbered_match = re.match(r'^[\d\.\)\-\*]+\s*(.+)$', line)
                    if numbered_match:
                        reason = numbered_match.group(1).strip()
                        if reason and reason not in rejection_reasons:
                            rejection_reasons.append(reason)
                            if len(rejection_reasons) >= REQUIRED_REJECTION_REASONS:
                                break
        
        # Parse confidence score
        confidence_pattern = r"CONFIDENCE_SCORE:\s*(\d+(?:\.\d+)?)"
        confidence_match = re.search(confidence_pattern, model_output, re.IGNORECASE)
        
        if confidence_match:
            try:
                raw_score = confidence_match.group(1)
                confidence_score = Decimal(raw_score).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_EVEN
                )
            except (InvalidOperation, ValueError) as e:
                logger.warning(
                    f"[CONFIDENCE_PARSE_WARN] raw={raw_score} error={str(e)}"
                )
        
        # If no explicit confidence found, try to extract any number 0-100
        if confidence_score is None:
            number_pattern = r'\b(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|confidence)?'
            for match in re.finditer(number_pattern, model_output, re.IGNORECASE):
                try:
                    value = Decimal(match.group(1))
                    if Decimal("0") <= value <= Decimal("100"):
                        confidence_score = value.quantize(
                            Decimal("0.01"),
                            rounding=ROUND_HALF_EVEN
                        )
                        break
                except (InvalidOperation, ValueError):
                    continue
        
        # Validate results
        if len(rejection_reasons) < REQUIRED_REJECTION_REASONS:
            # Pad with generic reasons if model didn't provide enough
            while len(rejection_reasons) < REQUIRED_REJECTION_REASONS:
                rejection_reasons.append(
                    f"[AUTO] Insufficient adversarial analysis - reason {len(rejection_reasons) + 1} not provided"
                )
            logger.warning(
                f"[REJECTION_REASONS_PADDED] found={len(rejection_reasons) - (REQUIRED_REJECTION_REASONS - len(rejection_reasons))}"
            )
        
        if confidence_score is None:
            # Default to low confidence if not parseable (fail-safe)
            confidence_score = Decimal("50.00")
            logger.warning("[CONFIDENCE_DEFAULT] Using default 50.00")
        
        # Clamp confidence to valid range
        if confidence_score < Decimal("0"):
            confidence_score = Decimal("0.00")
        elif confidence_score > Decimal("100"):
            confidence_score = Decimal("100.00")
        
        return (rejection_reasons[:REQUIRED_REJECTION_REASONS], confidence_score)
    
    async def _invoke_model(
        self,
        prompt: str,
        correlation_id: str
    ) -> str:
        """
        Invoke Ollama model with timeout.
        
        Reliability Level: L6 Critical
        Input Constraints: prompt must be non-empty
        Side Effects: Network I/O to Ollama
        
        Args:
            prompt: The adversarial prompt
            correlation_id: Tracking ID
            
        Returns:
            Model response text
            
        Raises:
            asyncio.TimeoutError: If model exceeds timeout
            RuntimeError: If no ollama_callback configured
        """
        if self._ollama_callback is None:
            raise RuntimeError(
                "[MODEL_NOT_CONFIGURED] No ollama_callback provided"
            )
        
        logger.info(
            f"[MODEL_INVOKE] model={self._model_name} "
            f"correlation_id={correlation_id} timeout={self._timeout_seconds}s"
        )
        
        try:
            response = await asyncio.wait_for(
                self._ollama_callback(self._model_name, prompt),
                timeout=self._timeout_seconds
            )
            
            logger.info(
                f"[MODEL_RESPONSE] correlation_id={correlation_id} "
                f"response_length={len(response)}"
            )
            
            return response
            
        except asyncio.TimeoutError:
            logger.error(
                f"[{ERROR_PRE_AUDIT_TIMEOUT}] correlation_id={correlation_id} "
                f"timeout={self._timeout_seconds}s"
            )
            raise

    async def audit_signal(
        self,
        signal: TradeSignal,
        correlation_id: Optional[str] = None
    ) -> AuditResult:
        """
        Execute adversarial audit on trade signal.
        
        Reliability Level: L6 Critical
        Input Constraints: Signal must have valid data
        Side Effects: Invokes Ollama, writes audit logs
        
        Args:
            signal: The trade signal to audit
            correlation_id: Optional override for tracking ID
            
        Returns:
            AuditResult with decision and reasoning
        """
        cid = correlation_id or signal.correlation_id
        start_time_ms = int(time.time() * 1000)
        
        logger.info(
            f"[AUDIT_START] symbol={signal.symbol} action={signal.action} "
            f"price={signal.price} correlation_id={cid}"
        )
        
        # Build adversarial prompt
        prompt = self._build_adversarial_prompt(signal)
        
        try:
            # Invoke model with timeout (Property 1)
            raw_output = await self._invoke_model(prompt, cid)
            
            # Parse response (Property 2)
            rejection_reasons, confidence_score = self.parse_rejection_reasons(
                raw_output
            )
            
            # Apply confidence threshold (Property 3)
            approved = confidence_score >= self._confidence_threshold
            
            end_time_ms = int(time.time() * 1000)
            execution_time_ms = end_time_ms - start_time_ms
            
            result = AuditResult(
                correlation_id=cid,
                confidence_score=confidence_score,
                rejection_reasons=rejection_reasons,
                approved=approved,
                audit_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                execution_time_ms=execution_time_ms,
                model_used=self._model_name,
                raw_model_output=raw_output
            )
            
            # Log decision
            decision = "APPROVED" if approved else "REJECTED"
            logger.info(
                f"[AUDIT_DECISION] decision={decision} "
                f"confidence={confidence_score} threshold={self._confidence_threshold} "
                f"correlation_id={cid} execution_time_ms={execution_time_ms}"
            )
            
            # Write audit record
            if self._audit_writer is not None:
                try:
                    await self._audit_writer(result)
                except Exception as e:
                    logger.error(
                        f"[AUDIT_WRITE_FAIL] correlation_id={cid} error={str(e)}"
                    )
            
            return result
            
        except asyncio.TimeoutError:
            end_time_ms = int(time.time() * 1000)
            execution_time_ms = end_time_ms - start_time_ms
            
            result = AuditResult(
                correlation_id=cid,
                confidence_score=Decimal("0.00"),
                rejection_reasons=["[TIMEOUT] Model response exceeded 30 seconds"],
                approved=False,
                audit_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                execution_time_ms=execution_time_ms,
                model_used=self._model_name,
                error_code=ERROR_PRE_AUDIT_TIMEOUT,
                error_message=f"Model timeout after {self._timeout_seconds}s"
            )
            
            logger.error(
                f"[AUDIT_TIMEOUT] correlation_id={cid} "
                f"execution_time_ms={execution_time_ms}"
            )
            
            if self._audit_writer is not None:
                try:
                    await self._audit_writer(result)
                except Exception as e:
                    logger.error(f"[AUDIT_WRITE_FAIL] error={str(e)}")
            
            return result
            
        except Exception as e:
            end_time_ms = int(time.time() * 1000)
            execution_time_ms = end_time_ms - start_time_ms
            
            result = AuditResult(
                correlation_id=cid,
                confidence_score=Decimal("0.00"),
                rejection_reasons=[f"[ERROR] {str(e)}"],
                approved=False,
                audit_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                execution_time_ms=execution_time_ms,
                model_used=self._model_name,
                error_code="AUDIT_ERROR",
                error_message=str(e)
            )
            
            logger.error(
                f"[AUDIT_ERROR] correlation_id={cid} error={str(e)}"
            )
            
            if self._audit_writer is not None:
                try:
                    await self._audit_writer(result)
                except Exception as write_error:
                    logger.error(f"[AUDIT_WRITE_FAIL] error={str(write_error)}")
            
            return result
    
    def evaluate_confidence(
        self,
        confidence_score: Decimal
    ) -> tuple:
        """
        Evaluate confidence score against threshold.
        
        Reliability Level: L6 Critical
        Input Constraints: confidence_score must be Decimal in [0, 100]
        Side Effects: None
        
        Args:
            confidence_score: The confidence score to evaluate
            
        Returns:
            Tuple of (bool approved, str decision_reason)
        """
        if not isinstance(confidence_score, Decimal):
            raise TypeError(
                f"[DECIMAL_VIOLATION] confidence_score is not Decimal: {type(confidence_score)}"
            )
        
        if confidence_score < Decimal("0") or confidence_score > Decimal("100"):
            raise ValueError(
                f"[CONFIDENCE_RANGE] Score out of range: {confidence_score}"
            )
        
        approved = confidence_score >= self._confidence_threshold
        
        if approved:
            reason = (
                f"Confidence {confidence_score} >= threshold {self._confidence_threshold}"
            )
        else:
            reason = (
                f"Confidence {confidence_score} < threshold {self._confidence_threshold}"
            )
        
        return (approved, reason)


# =============================================================================
# INTEGRATION WITH AURA-FULL MCP
# =============================================================================

async def create_ollama_callback_from_mcp(
    mcp_tool_caller: Callable[[str, str, Dict[str, Any]], Awaitable[Any]]
) -> Callable[[str, str], Awaitable[str]]:
    """
    Create an Ollama callback that uses the aura-full MCP ollama_consult tool.
    
    Reliability Level: L5 High
    Input Constraints: mcp_tool_caller must be valid MCP tool invoker
    Side Effects: Network I/O via MCP
    
    Args:
        mcp_tool_caller: Function to call MCP tools (server, tool, args) -> result
        
    Returns:
        Async callback compatible with PreTradeAuditModule
    """
    async def ollama_callback(model: str, prompt: str) -> str:
        """Invoke ollama_consult via aura-full MCP."""
        result = await mcp_tool_caller(
            "aura-full",
            "ollama_consult",
            {
                "model": model,
                "prompt": prompt,
                "temperature": 0.3  # Lower temperature for more consistent reasoning
            }
        )
        
        # Extract response text from MCP result
        if isinstance(result, dict):
            return result.get("response", str(result))
        return str(result)
    
    return ollama_callback

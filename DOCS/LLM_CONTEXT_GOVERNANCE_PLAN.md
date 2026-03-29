# LLM Context Governance Plan

## Project Autonomous Alpha — Phase 6

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.2.0
**Status:** IN PROGRESS — C1 + C2 Complete
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2025-07-15

---

## 1. Executive Summary

The LLM is a governed dependency, not an open-ended assistant. Every byte entering and exiting the model must be deterministic, auditable, and budget-controlled.

This document defines the full governance layer that will wrap the AI Council's Bull/Bear debate path. The goal: zero ambiguity, zero silent truncation, zero uncontrolled context, zero optimistic parsing. If the governance layer cannot construct a valid, budget-compliant decision packet, the trade is REJECTED — no exceptions.

**Mandate:** FAIL CLOSED on any doubt.

---

## 2. Scope and Non-Negotiables

### In Scope

- All context entering LLM prompts (system prompt, signal fields, operational context, historical data)
- All output parsing and verdict extraction
- Token budget enforcement and overflow policy
- Prompt version control and model fingerprinting
- Golden regression suite for decision determinism
- Observability: every decision packet logged with full lineage

### Non-Negotiables

| # | Rule | Consequence of Violation |
|---|------|--------------------------|
| 1 | No uncontrolled raw context enters the LLM | Trade REJECTED |
| 2 | No silent truncation of any field | Trade REJECTED |
| 3 | No optimistic parsing of model output | Default to REJECTED |
| 4 | No "best effort" decision approval | System halt |
| 5 | No floating-point math for any numeric field | Build failure |
| 6 | Every decision packet is immutably logged before LLM call | Audit violation |
| 7 | Token budget exceeded = REJECT (not truncate-and-hope) | Trade REJECTED |
| 8 | Prompt version mismatch = REJECT | Trade REJECTED |
| 9 | Model fingerprint missing = REJECT | Trade REJECTED |
| 10 | Ambiguous verdict = REJECTED (never UNCERTAIN → retry) | Trade REJECTED |

---

## 3. Failure Modes We Must Prevent (C1 Deliverable)

### 3.1 Current Architecture Summary

The AI decision path runs through:

```
TradingView Signal
  → webhook.py (STEP 10: conduct_debate)
    → get_ai_council() → AICouncil (OpenRouter) | OllamaAICouncil (local)
      → BULL_PROMPT_TEMPLATE.format(symbol, side, price, quantity)
      → BEAR_PROMPT_TEMPLATE.format(symbol, side, price, quantity)
      → _call_openrouter() | _call_ollama()
      → _parse_verdict() [regex: "VERDICT: APPROVED|REJECTED"]
      → _compute_consensus() [both must APPROVE]
    → DebateResult persisted to ai_debates table
  → confidence_arbiter.py (RGI: adjusted = llm × trust × health, 95% gate)
  → HITL gateway
```

**Files audited:** ai_council.py (1180 lines), ollama_context_builder.py (170 lines), sovereign_intel.py (450 lines), confidence_arbiter.py (300 lines), debate_memory.py (300 lines), ollama_health.py (240 lines), webhook.py (830 lines), pre_trade_audit.py, ai_council_system_prompt.txt (7 lines).

### 3.2 Critical Failure Mode Inventory

Each failure mode is assigned a severity grade:

- **S1 (CRITICAL):** Can directly cause incorrect trade execution or capital loss
- **S2 (SEVERE):** Can cause systematic decision degradation or audit gaps
- **S3 (MODERATE):** Can cause latency, observability, or reliability issues

---

#### FM-01: No Retry Logic — Single Timeout = Permanent REJECTED

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | `ai_council.py` → `_call_openrouter()` (line ~310), `_call_ollama()` (line ~710) |
| **Current Behavior** | A single `httpx.TimeoutException` after 30s (OpenRouter) or 60s (Ollama) returns `(error_msg, ModelVerdict.ERROR)`. ERROR in consensus = score 0, final_verdict=False. No retry. |
| **Failure Scenario** | Ollama is momentarily busy loading a model layer (common with qwen3:8b on 8GB VRAM). First request times out. Signal is permanently REJECTED. A valid trade opportunity is lost with no second chance. |
| **Impact** | False negative. Systematic rejection of valid signals during model warmup or transient load. |
| **Current Safeguard** | ERROR defaults to REJECTED (safe from capital loss). |
| **Governance Fix** | Phase 6 will NOT add retry. Retry introduces non-determinism and latency risk. Instead: (a) pre-warm model via health check before accepting signals, (b) log timeout as `FM-01-TIMEOUT` with full context, (c) operator dashboard shows timeout frequency for manual intervention. The fail-closed behavior is CORRECT. |

---

#### FM-02: Synchronous Hot Path — 30–120s Latency Blocks HTTP Response

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `webhook.py` STEP 10 (line ~504-530) |
| **Current Behavior** | `conduct_debate()` is awaited inline in the webhook handler. Bull and Bear calls run concurrently (`asyncio.gather`), but the webhook response is blocked until both complete. Ollama with qwen3:8b on NAS hardware: 10-30s per call. OpenRouter free tier: 5-30s per call. Total: 10-60s blocking. |
| **Failure Scenario** | TradingView has a ~30s webhook timeout. If Ollama is slow, TradingView marks the webhook as failed and may retry, causing duplicate signal processing. Meanwhile, the HTTP connection is held open consuming server resources. |
| **Impact** | Webhook timeout → TradingView retry → potential duplicate trades. Resource exhaustion under burst signals. |
| **Current Safeguard** | HMAC signature verification prevents unauthorized signals. Duplicate detection via correlation_id exists in signals table. |
| **Governance Fix** | Phase 6 does not restructure the async architecture (out of scope). But: (a) decision packet construction must be < 50ms, (b) prompt must be pre-validated before LLM call, (c) if packet construction fails, REJECT immediately without calling LLM (saves 30-60s). Document the latency risk for future Phase 7 async refactor. |

---

#### FM-03: Context Builder Never Wired — AI Debates With Zero Historical Context

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | `ollama_context_builder.py` (fully implemented, 170 lines) — NEVER IMPORTED in `webhook.py` |
| **Current Behavior** | `build_context_block()` exists and works. It queries the last 3 debates for the same symbol, reads execution mode, reads guardian lock state. But `webhook.py` STEP 10 calls `council.conduct_debate(correlation_id, symbol, side, price, quantity)` — raw signal fields ONLY. No context injection. |
| **Failure Scenario** | BTCZAR was REJECTED 3 consecutive times in the last hour due to high volatility. A new BTCZAR signal arrives. The LLM has no memory of the prior rejections and evaluates the signal as if it is the first one ever. It may APPROVE a signal that the system has been consistently rejecting. |
| **Impact** | Stateless decisions. AI cannot learn from recent history intra-session. Contradictory verdicts for similar signals. |
| **Current Safeguard** | None for context. The RGI confidence arbiter provides some protection via trust_probability, but this is a separate post-debate gate, not prompt context. |
| **Governance Fix** | Phase 6 C4 (DecisionPacketBuilder) will wire `build_context_block()` into the prompt. Context becomes a REQUIRED field in the decision packet. If context retrieval fails, REJECT (do not proceed blind). |

---

#### FM-04: Regex-Only Verdict Parsing — Fragile Against Model Output Variations

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | `ai_council.py` → `AICouncil._parse_verdict()` (line ~395), `OllamaAICouncil._parse_verdict()` (line ~790) |
| **Current Behavior** | Two DIFFERENT parsers exist: |
| | **AICouncil** (OpenRouter): Checks `"VERDICT: APPROVED"` or `"VERDICT:APPROVED"` in uppercased content. Falls back to checking if `"APPROVED"` exists without `"REJECTED"` (and vice versa). Unclear = `REJECTED`. |
| | **OllamaAICouncil** (Ollama): Same checks, but unclear = `UNCERTAIN` (not REJECTED). |
| **Failure Scenario** | Model outputs: `"The trade should be APPROVED based on the analysis. However, the risk is significant. VERDICT: REJECTED"` — contains both APPROVED and REJECTED. AICouncil parser falls through to the "unclear" branch → REJECTED. But if model outputs `"I would NOT have APPROVED this. VERDICT: REJECTED"` — the presence of "APPROVED" before "REJECTED" in the fallback branch causes ambiguity. |
| **Impact** | Inconsistent verdicts between backends. OllamaAICouncil can return UNCERTAIN which has undefined consensus behavior (currently maps to score=0, but creates audit ambiguity). |
| **Current Safeguard** | Both parsers default to REJECTED/UNCERTAIN on ambiguity (fail-closed). |
| **Governance Fix** | Phase 6 C8 (StrictOutputSchema) will define a JSON output schema. The model must return `{"verdict": "APPROVED"}` or `{"verdict": "REJECTED"}` — nothing else. Phase 6 C9 (RejectOnAmbiguityPolicy) will reject any response that does not parse to exactly one of two valid values. The UNCERTAIN verdict will be eliminated from the output contract. |

---

#### FM-05: No Token Counting — Silent Truncation Possible

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | `ai_council.py` → `_call_openrouter()` payload `max_tokens: 500`, `_call_ollama()` options `num_predict: 512` |
| **Current Behavior** | System prompt is loaded with a 512-char budget guard (truncates at character level, not token level). User prompts (BULL/BEAR templates) have no budget guard at all — they grow with symbol name length and price/quantity string length. Total prompt size is never measured in tokens. OpenRouter `max_tokens: 500` limits OUTPUT tokens only. If the combined system+user prompt exceeds the model's context window, the API silently truncates the INPUT. |
| **Failure Scenario** | A future change adds more context to the prompt (e.g., wiring the context builder). The total prompt exceeds qwen3:8b's 32K context window (unlikely with current templates, but no guard prevents it). More realistically: the 512-char system prompt budget uses CHARACTERS, not tokens. A 512-char prompt may be 150-200 tokens, wasting budget, or it may be 300+ tokens for multi-byte characters, leaving less room for the actual signal. |
| **Impact** | Unpredictable token allocation. No guarantee the model sees the full prompt. No guarantee the model has enough output tokens to produce the verdict line. |
| **Current Safeguard** | Current prompts are small (~400 chars each). Risk is LOW today but will increase when context injection is wired. |
| **Governance Fix** | Phase 6 C6 (TokenBudgetGuard) will implement real token counting using a tokenizer or character-based estimation with a safety margin. Budget tiers: system prompt (T1), signal fields (T1), context block (T2), output reserve (T1). If total exceeds budget, C7 (OverflowRejectPolicy) REJECTS — never truncates. |

---

#### FM-06: No Output Schema — Free-Form Text Parsing

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `ai_council.py` → prompt templates (line ~170-220) |
| **Current Behavior** | Prompt instructs: `"Deliver a concise 2-sentence analysis, then terminate with exactly: VERDICT: APPROVED or VERDICT: REJECTED — No additional text after the VERDICT line."` This is a natural language instruction, not a schema. The model frequently adds text after the verdict line (observed in test outputs). Some models add `\n\nNote:` or reasoning after the verdict. |
| **Failure Scenario** | Model outputs: `"VERDICT: APPROVED\n\nNote: This assumes the exchange is operating normally."` The regex parser still finds `VERDICT: APPROVED` so this works TODAY. But if the model outputs `"VERDICT: APPROVED\nHowever, I would also note this could be REJECTED under different conditions"` the parser sees BOTH words and enters the ambiguity branch. |
| **Impact** | Unreliable verdict extraction. Parser correctness depends on model discipline (which varies by model version, temperature, and prompt phrasing). |
| **Current Safeguard** | Temperature set to 0.3 (reduces variation). Ambiguity defaults to REJECTED. |
| **Governance Fix** | Phase 6 C8 (StrictOutputSchema) will require JSON output: `{"verdict": "APPROVED", "reasoning": "..."}`. Phase 6 C9 (RejectOnAmbiguityPolicy) will reject any response that fails JSON parsing or contains a verdict value other than APPROVED/REJECTED. |

---

#### FM-07: Dual Parse Behavior Between Backends

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `AICouncil._parse_verdict()` vs `OllamaAICouncil._parse_verdict()` |
| **Current Behavior** | AICouncil (OpenRouter): Unclear verdict → `ModelVerdict.REJECTED`. OllamaAICouncil (Ollama): Unclear verdict → `ModelVerdict.UNCERTAIN`. These are different code paths with different safety guarantees. |
| **Failure Scenario** | A signal is routed to the Ollama backend. The model's response is ambiguous. OllamaAICouncil returns UNCERTAIN. `_compute_consensus()` maps UNCERTAIN to `(0, False)` — safe. But the audit trail shows `UNCERTAIN` instead of `REJECTED`, creating confusion about whether the rejection was a fail-safe or a deliberate verdict. Worse: if consensus logic ever changes to treat UNCERTAIN differently (e.g., "retry on UNCERTAIN"), this creates a security hole. |
| **Impact** | Audit ambiguity. Divergent behavior between backends for identical inputs. Future maintenance risk. |
| **Current Safeguard** | Both paths ultimately result in final_verdict=False. |
| **Governance Fix** | Phase 6 will eliminate UNCERTAIN from the output contract entirely. Both backends will use a single, shared parsing function. The only valid outputs are APPROVED, REJECTED, or PARSE_ERROR. PARSE_ERROR always maps to REJECTED. |

---

#### FM-08: Sovereign Intel Layer Never Wired — Decision-Integrity Gap

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL (upgraded from S2; see rationale below) |
| **Location** | `sovereign_intel.py` (450 lines, fully implemented) — NEVER IMPORTED in `webhook.py` |
| **Current Behavior** | `sovereign_intel.py` implements: RAG queries for similar past debates, ML confidence predictions, symbol-specific historical win rates, RGI trust probability retrieval. None of this is called. The LLM receives only 4 raw signal fields: symbol, side, price, quantity. |
| **Failure Scenario** | The AI evaluates BTCZAR BUY at 1,500,000 ZAR with no knowledge of: whether this price is 5% above or 5% below the 24h average, whether the last 10 BTC trades were all losses, whether the ML model's confidence for this signal is 30% or 95%, whether the Reward Governor's trust for this symbol is degraded. |
| **Impact** | **Decision-integrity gap, not merely a feature gap.** The LLM is asked to render a SOVEREIGN TIER verdict — APPROVED or REJECTED — on a packet containing only 4 fields (symbol, side, price, quantity). Without historical win rate, ML confidence, and RGI trust, the model cannot distinguish between a high-conviction signal and a noise signal. The verdict is structurally uninformed: the model has no basis to approve OR reject beyond surface-level price heuristics. This is not "missing enrichment" — it is an integrity violation because the system claims the verdict is evidence-based (per the system prompt: "Base every judgment solely on the trade signal fields provided") while withholding the evidence that would make the judgment sound. A verdict produced on incomplete evidence is not a valid verdict; it is a coin flip decorated with reasoning. |
| **Current Safeguard** | The RGI confidence arbiter (post-debate) provides some correction via trust_probability, but this happens AFTER the debate — the LLM never sees it. The post-hoc gate cannot compensate for a fundamentally uninformed verdict. |
| **Governance Fix** | Phase 6 C4 (DecisionPacketBuilder) will define which sovereign_intel fields are injected. C3 (ContextPriorityPolicy) will tier them. Key sovereign_intel fields (historical win rate, ML confidence, RGI trust indicator) will be classified as Tier 1 (REQUIRED) or high Tier 2 (IMPORTANT) — not optional enrichment. If the sovereign_intel layer is unreachable AND the fields are Tier 1, the trade is REJECTED. |
| **Upgrade Rationale** | Reclassified from S2 to S1 because: (1) the system prompt mandates evidence-based judgment but the evidence is withheld, (2) a verdict on 4 fields alone cannot meet the "certainty is required for APPROVED" standard, (3) wiring sovereign_intel is a prerequisite for decision-packet integrity — without it, the packet is structurally incomplete regardless of how well the other subsystems work. |

---

#### FM-09: Pre-Trade Audit Completely Disconnected

| Attribute | Detail |
|-----------|--------|
| **Severity** | S3 — MODERATE |
| **Location** | `pre_trade_audit.py` — NEVER IMPORTED in `webhook.py` |
| **Current Behavior** | `pre_trade_audit.py` implements an adversarial audit using DeepSeek-R1 that generates 3 rejection reasons per signal. It is a completely separate decision path that is not wired into the hot path. |
| **Failure Scenario** | The pre-trade audit may have valuable adversarial insights that could inform the bull/bear debate, but they are never available. |
| **Impact** | Wasted implementation. No adversarial challenge to the bull/bear consensus. |
| **Current Safeguard** | N/A — the module is unused. |
| **Governance Fix** | Phase 6 will NOT wire pre_trade_audit into the hot path. Reason: it uses a DIFFERENT model (DeepSeek-R1) with separate token budgets, latency characteristics, and failure modes. Wiring it in would double the LLM latency and create a third parsing path. It will be documented as a future Phase 7 candidate for offline batch audit. |

---

#### FM-10: No Prompt Versioning — v1.0.0 Hardcoded

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `ai_council_system_prompt.txt` line 1: `# SYSTEM PROMPT v1.0.0` |
| **Current Behavior** | The system prompt has a version comment (`v1.0.0`) but this is a human-readable comment, not a machine-tracked version. The prompt templates (`BULL_PROMPT_TEMPLATE`, `BEAR_PROMPT_TEMPLATE`) have NO version at all. If someone edits a prompt, there is no audit trail of what version produced which debate. |
| **Failure Scenario** | An operator modifies the bear prompt to be more aggressive. Historical debates were produced with the old prompt. There is no way to determine which prompt version produced which verdict in the `ai_debates` table. Regression analysis is impossible. |
| **Impact** | No prompt lineage. Cannot reproduce past decisions. Cannot A/B test prompt changes. |
| **Current Safeguard** | None. |
| **Governance Fix** | Phase 6 C10 (PromptVersionRegistry) will hash every prompt version (SHA-256) and store the hash alongside each debate record. Prompt changes require version bump. Hash mismatch = REJECT. |

---

#### FM-11: No Model Fingerprinting — No Audit Trail of Model Identity

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `ai_council.py` — model name stored nowhere in debate result |
| **Current Behavior** | `DebateResult` contains: correlation_id, bull_reasoning, bear_reasoning, bull_verdict, bear_verdict, consensus_score, final_verdict. It does NOT contain: which model produced the bull reasoning, which model produced the bear reasoning, what model version/hash was used, what quantization was active (for Ollama). |
| **Failure Scenario** | The operator switches from `qwen3:8b` to `qwen3:4b` for faster inference. Historical debates show a change in verdict patterns, but there is no way to correlate this with the model change. |
| **Impact** | Cannot attribute decisions to specific model versions. Cannot detect model drift. Cannot perform regression analysis across model changes. |
| **Current Safeguard** | None. |
| **Governance Fix** | Phase 6 C11 (ModelFingerprintLogger) will record: model name, model version/tag, quantization level, Ollama model digest (SHA-256), and backend type (OPENROUTER/OLLAMA) in every debate record. |

---

#### FM-12: System Prompt Budget Uses Characters, Not Tokens

| Attribute | Detail |
|-----------|--------|
| **Severity** | S3 — MODERATE |
| **Location** | `ai_council.py` line ~134: `_SYSTEM_PROMPT_BUDGET: int = 512` |
| **Current Behavior** | `_load_system_prompt()` truncates at 512 CHARACTERS. But LLM context windows are measured in TOKENS. For English text, 1 token ≈ 4 characters (GPT-style) or 1 token ≈ 3.5 characters (Qwen). For the current system prompt (~380 characters), this is approximately 95-110 tokens — well within budget. |
| **Failure Scenario** | If the system prompt is expanded to include governance rules (which Phase 6 will do), a 512-character limit may be too restrictive OR may not correspond to the actual token budget needed. |
| **Impact** | Low today. Will become relevant when Phase 6 expands the system prompt. |
| **Current Safeguard** | Current prompt is well under 512 characters. |
| **Governance Fix** | Phase 6 C6 (TokenBudgetGuard) will replace character-based budgets with token-based budgets using a deterministic estimation function. Budget tiers will be defined in tokens, not characters. |

---

#### FM-13: `/no_think` Prefix in Prompt Templates

| Attribute | Detail |
|-----------|--------|
| **Severity** | S3 — MODERATE |
| **Location** | `ai_council.py` → `BULL_PROMPT_TEMPLATE` and `BEAR_PROMPT_TEMPLATE` (line ~170) |
| **Current Behavior** | Both templates start with `/no_think` — a Qwen3-specific instruction to suppress the model's internal reasoning chain ("thinking mode"). This is correct for qwen3:8b but is meaningless noise for non-Qwen models (Mistral, Gemini, etc. on OpenRouter). |
| **Failure Scenario** | On OpenRouter, Mistral-7B receives `/no_think` as the first line of the prompt. Mistral has no concept of this instruction. It may: (a) ignore it (likely), (b) interpret it as part of the signal, (c) be confused by it. |
| **Impact** | Low. Most models will ignore unknown directives. But it wastes tokens on OpenRouter and is model-specific coupling. |
| **Current Safeguard** | The prompt is small enough that the wasted tokens don't cause truncation. |
| **Governance Fix** | Phase 6 C10 (PromptVersionRegistry) will support backend-specific prompt variants. The `/no_think` prefix will only be injected for Qwen-family models on Ollama. OpenRouter prompts will omit it. |

---

#### FM-14: Required-vs-Optional Context Not Explicitly Governed

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | System-wide — no field criticality classification exists anywhere in the codebase |
| **Current Behavior** | The prompt templates inject exactly 4 signal fields (symbol, side, price, quantity). The context builder (if it were wired) would add execution mode, guardian state, and last 3 debates. The sovereign intel layer (if it were wired) would add RAG results, ML confidence, win rate, and RGI trust. But NOWHERE in the system is any field classified as REQUIRED vs OPTIONAL vs NEVER. Every field is implicitly "include if available, skip if not." |
| **Failure Scenario** | Token budgeting and overflow handling cannot be implemented safely without field criticality rules. Consider: the token budget is 2048 tokens. System prompt takes 150. Signal fields take 100. That leaves 1798 for context + output reserve. If we inject context builder (600 chars ≈ 170 tokens) and sovereign intel (1500 chars ≈ 430 tokens), we use ~600 tokens for context, leaving ~1200 for output reserve. But without explicit REQUIRED/OPTIONAL classification, overflow handling has no policy: if we run over budget, WHICH fields get dropped? If we drop the RGI trust indicator because it was the last field added, the verdict loses its most important context. If we drop the symbol because it was "just a string," the verdict is meaningless. Without classification, any overflow policy is arbitrary and unsafe. |
| **Impact** | Token budgeting (C6), overflow rejection (C7), and compact encoding (C5) all depend on field criticality. Without it, these subsystems cannot make deterministic decisions about what to include, what to drop, and when to REJECT. The governance layer collapses to "best effort" — violating Non-Negotiable #4. |
| **Current Safeguard** | None. The concept of field criticality does not exist in the current codebase. |
| **Governance Fix** | Phase 6 C2 (DECISION_PACKET_SPEC.md) will define every field with an explicit classification: REQUIRED (Tier 1 — omission = REJECT), IMPORTANT (Tier 2 — include if budget allows, log if omitted), OPTIONAL (Tier 3 — include only with surplus budget), NEVER (Tier 4 — explicitly forbidden). C3 (ContextPriorityPolicy) will enforce these tiers at construction time. C7 (OverflowRejectPolicy) will use them to determine whether to drop-and-log or REJECT-and-halt. |

---

#### FM-15: No Packet Hash / Context Checksum for Forensic Traceability

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | System-wide — no packet identity mechanism exists |
| **Current Behavior** | The debate result contains `correlation_id`, `bull_reasoning`, `bear_reasoning`, `bull_verdict`, `bear_verdict`, `consensus_score`, and `final_verdict`. But the INPUT to the LLM — the exact prompt that was sent — is not hashed or checksummed. There is no `packet_hash` field. If the prompt templates change, if context is injected differently, or if a field is silently dropped, the audit trail has no way to detect this. Prompt versioning (FM-10) and model fingerprinting (FM-11) each capture one dimension of lineage, but without a packet hash they are incomplete: we know WHICH prompt template and WHICH model, but not WHAT EXACT INPUT the model received. |
| **Failure Scenario** | An operator investigates a suspicious APPROVED verdict from 3 days ago. They can see the prompt template version and model fingerprint, but cannot reconstruct the exact input. Was the context builder wired at that point? Which sovereign_intel fields were injected? Were any fields truncated by the budget guard? Without a packet hash, forensic reconstruction requires re-running the entire pipeline — which may produce different results if any parameter changed. |
| **Impact** | Incomplete audit lineage. Prompt versioning + model fingerprinting answer "what template?" and "what model?" but not "what exact input?" Regression testing cannot verify that a known packet hash produces a known verdict. Forensic investigation is non-deterministic. |
| **Current Safeguard** | None. |
| **Governance Fix** | Phase 6 C2 (DECISION_PACKET_SPEC.md) will define a `packet_hash` field: SHA-256 of the complete, assembled decision packet (all fields concatenated in canonical order, after compact encoding, before LLM submission). This hash is stored in the `ai_debates` record alongside prompt_version_hash and model_fingerprint, completing the three-dimensional audit lineage: (packet_hash × prompt_version × model_fingerprint) → verdict. C13 (GoldenDecisionRegressionSuite) will use packet hashes as test vector identifiers. |

---

### 3.3 Unwired Components Summary

| Component | Location | Lines | Status | Phase 6 Action |
|-----------|----------|-------|--------|----------------|
| `ollama_context_builder.py` | `app/logic/` | 170 | FULLY IMPLEMENTED, never imported in webhook | Wire via DecisionPacketBuilder (C4). Failure = REJECT. |
| `sovereign_intel.py` | `app/logic/` | 450 | FULLY IMPLEMENTED, never imported in webhook | Wire Tier 2 fields via DecisionPacketBuilder (C4). Failure = log + continue. |
| `pre_trade_audit.py` | `app/logic/` | ~300 | IMPLEMENTED, never imported in webhook | DO NOT WIRE in Phase 6. Future Phase 7 candidate. |

### 3.4 Safety Features Already Working (DO NOT BREAK)

These safety features are CORRECT and must be preserved through all Phase 6 changes:

| # | Feature | Location | Behavior |
|---|---------|----------|----------|
| 1 | Default FALSE | `_compute_consensus()` | Trade only proceeds on unanimous APPROVED |
| 2 | Unanimous consensus | `_compute_consensus()` | Both bull AND bear must APPROVE |
| 3 | Error → REJECTED | Both `_compute_consensus()` methods | Any ERROR verdict = score 0, final_verdict=False |
| 4 | HMAC signature verification | `webhook.py` | Prevents unauthorized signal injection |
| 5 | Decimal-only math | All financial calculations | Zero-Float Mandate enforced |
| 6 | Immutable audit trail | `ai_debates` table | Reasoning saved EVEN on rejection |
| 7 | Correlation ID tracing | All functions | Full lineage from signal to verdict |
| 8 | RGI 95% confidence gate | `confidence_arbiter.py` | Post-debate gate: adjusted = llm × trust × health |
| 9 | Temperature 0.3 | Both backends | Reduces output variation |
| 10 | HITL gate | `webhook.py` STEP 12+ | Human approval required after AI consensus |

### 3.5 Failure Mode Priority Matrix

| Priority | Failure Modes | Phase 6 Sub-Phase | Rationale |
|----------|---------------|-------------------|-----------|
| P0 — Block | FM-03, FM-04, FM-05, FM-06, FM-07, FM-08, FM-14 | C2, C3, C4, C6, C7, C8, C9 | Context blindness + parsing fragility + ungoverned field criticality + uninformed verdicts = structurally unsound decisions |
| P1 — Critical | FM-10, FM-11, FM-15 | C2, C10, C11 | No audit lineage (prompt + model + packet) = cannot investigate, cannot regress |
| P2 — Important | FM-01, FM-02 | C4, C12 | Operational reliability (timeout, latency) |
| P3 — Track | FM-09, FM-12, FM-13 | C5, C10 | Low impact today, documented for future phases |

---

## 4. Architecture Overview (Stub — C2+)

> To be completed in C2. Will contain:
>
> - Decision Packet schema with field-level specification
> - Context Priority Policy tiers
> - Token Budget allocation table
> - Prompt construction pipeline diagram

---

## 5. Decision Packet Specification (C2 — COMPLETE)

**Delivered:** [`DOCS/DECISION_PACKET_SPEC.md`](DECISION_PACKET_SPEC.md)

Defines the complete Decision Packet schema (version `DPv1`) with:

- 9 sections (A–I) in fixed order
- 28 fields across T1/T2/T3/T4 classifications
- Bounded max sizes for every field
- Missing data flags and omission rules
- SHA-256 packet hash for forensic traceability
- Compact encoding rules optimized for qwen3:8b
- Token budget worksheet (2,048 total; 1,200 packet; 512 output reserve)
- Validation rules (15 checks with error codes)
- Versioning policy (major/minor/patch)

---

## 6. Context Priority Policy (Stub — C3)

> To be completed in C3. Tier definitions:
>
> - Tier 1 (MUST-INCLUDE): Omission = REJECT
> - Tier 2 (SHOULD-INCLUDE): Included if token budget allows
> - Tier 3 (MAY-INCLUDE): Only if surplus budget after T1+T2
> - Tier 4 (NEVER-INCLUDE): Explicitly forbidden (raw user input, PII, etc.)

---

## 7. Subsystem Specifications (Stub — C4 through C12)

### 7.1 DecisionPacketBuilder (C4)

### 7.2 CompactFormatEncoder (C5)

### 7.3 TokenBudgetGuard (C6)

### 7.4 OverflowRejectPolicy (C7)

### 7.5 StrictOutputSchema (C8)

### 7.6 RejectOnAmbiguityPolicy (C9)

### 7.7 PromptVersionRegistry (C10)

### 7.8 ModelFingerprintLogger (C11)

### 7.9 DB-Aware Context Injection (C12)

> Each subsystem will be specified before implementation begins.

---

## 8. Integration Plan (Stub — C13)

> Integration with `ai_council.py`, `webhook.py`, `ollama_context_builder.py`.
> Must not break existing safety features (Section 3.4).

---

## 9. Golden Regression Suite (Stub — C13)

> Deterministic test vectors with known-good inputs → expected outputs.
> Will cover: packet construction, token budgeting, verdict parsing,
> ambiguity rejection, overflow rejection, prompt versioning.

---

## 10. Validation Checklist (Stub — C14)

> 14 specific validation requirements from Phase 6 mandate.

---

## 11. Observability (Stub — C12)

> Metrics, structured logging, and dashboard requirements for the governance layer.

---

## 12. Runbook (Stub — C14)

> To be delivered as `DOCS/LLM_CONTEXT_RUNBOOK.md`.

---

## 13. Regression Test Plan (Stub — C13)

> To be delivered as `DOCS/LLM_REGRESSION_TEST_PLAN.md`.

---

## 14. Change Log

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2025-07-15 | Kiro Agent | C1: Failure mode analysis (13 failure modes, 3 unwired components, 10 safety features) |
| 1.1.0 | 2026-03-29 | Kiro Agent | C1 amendments: FM-08 reclassified S2→S1 (decision-integrity gap), FM-14 added (field criticality ungoverned, S1), FM-15 added (no packet hash, S2). Priority matrix updated. Total: 15 failure modes. |
| 1.2.0 | 2026-03-29 | Kiro Agent | C2: Decision Packet Specification delivered (DECISION_PACKET_SPEC.md). DPv1 schema with 28 fields, 4 tiers, SHA-256 hashability, compact encoding, token budget worksheet. |

---

## 15. Final Verdict (Stub — C15)

> Must return exactly one of:
>
> - `PHASE 6 COMPLETE`
> - `PHASE 6 PARTIAL`
> - `PHASE 6 BLOCKED`

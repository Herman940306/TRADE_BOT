# LLM Context Governance Plan

## Project Autonomous Alpha — Phase 6 + Phase 7

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.7.0
**Status:** IN PROGRESS — C1 + C2 + C3 + C4 + C6 Complete (with governance amendments), Phase 7 (AI Backend Reliability) Complete, C5/C7+ pending
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2026-03-29

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
| **Governance Fix** | Phase 6 C4 (DecisionPacketBuilder) will wire context into the prompt. Context becomes a REQUIRED field in the decision packet. If context retrieval fails, REJECT (do not proceed blind). |

---

#### FM-04: Regex-Only Verdict Parsing — Fragile Against Model Output Variations

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | `ai_council.py` → `AICouncil._parse_verdict()` (line ~395), `OllamaAICouncil._parse_verdict()` (line ~790) |
| **Current Behavior** | Two DIFFERENT parsers exist: |
| | **AICouncil** (OpenRouter): Checks `"VERDICT: APPROVED"` or `"VERDICT:APPROVED"` in uppercased content. Falls back to checking if `"APPROVED"` exists without `"REJECTED"` (and vice versa). Unclear = `REJECTED`. |
| | **OllamaAICouncil** (Ollama): Same checks, but unclear = `UNCERTAIN` (not REJECTED). |
| **Failure Scenario** | Model outputs: `"The trade should be APPROVED based on the analysis. However, the risk is significant. VERDICT: REJECTED"` — contains both APPROVED and REJECTED. AICouncil parser falls through to the "unclear" branch → REJECTED. Ambiguity from mixed tokens in the output is unresolvable by regex. |
| **Impact** | Inconsistent verdicts between backends. OllamaAICouncil can return UNCERTAIN which has undefined consensus behavior (currently maps to score=0, but creates audit ambiguity). |
| **Current Safeguard** | Both parsers default to REJECTED/UNCERTAIN on ambiguity (fail-closed). |
| **Governance Fix** | Phase 6 C8 (StrictOutputSchema) will define a JSON output schema. The model must return `{"verdict": "APPROVED"}` or `{"verdict": "REJECTED"}` — nothing else. Phase 6 C9 (RejectOnAmbiguityPolicy) will reject any response that does not parse to exactly one of two valid values. The UNCERTAIN verdict will be eliminated from the output contract. |

---

#### FM-05: No Token Counting — Silent Truncation Possible

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | `ai_council.py` → `_call_openrouter()` payload `max_tokens: 500`, `_call_ollama()` options `num_predict: 512` |
| **Current Behavior** | System prompt is loaded with a 512-char budget guard (truncates at character level, not token level). User prompts (BULL/BEAR templates) have no budget guard at all. Total prompt size is never measured in tokens. OpenRouter `max_tokens: 500` limits OUTPUT tokens only. If the combined system+user prompt exceeds the model's context window, the API silently truncates the INPUT. |
| **Failure Scenario** | A future change adds more context to the prompt (e.g., wiring the context builder). The total prompt exceeds qwen3:8b's 32K context window (unlikely with current templates, but no guard prevents it). The 512-char system prompt budget uses CHARACTERS, not tokens. |
| **Impact** | Unpredictable token allocation. No guarantee the model sees the full prompt. No guarantee the model has enough output tokens to produce the verdict line. |
| **Current Safeguard** | Current prompts are small (~400 chars each). Risk is LOW today but will increase when context injection is wired. |
| **Governance Fix** | Phase 6 C6 (TokenBudgetGuard) will implement real token counting using a character-based estimation with a safety margin. Budget tiers: system prompt (T1), signal fields (T1), context block (T2), output reserve (T1). If total exceeds budget, C7 (OverflowRejectPolicy) REJECTS — never truncates. |

---

#### FM-06: No Output Schema — Free-Form Text Parsing

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `ai_council.py` → prompt templates |
| **Current Behavior** | Prompt instructs the model to deliver analysis then end with `VERDICT: APPROVED` or `VERDICT: REJECTED`. This is a natural language instruction, not a schema. The model frequently adds text after the verdict line. |
| **Failure Scenario** | Model outputs verdict followed by additional commentary containing the opposite verdict word, causing the parser to enter the ambiguity branch. |
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
| **Failure Scenario** | Audit trail shows `UNCERTAIN` instead of `REJECTED`, creating confusion about whether the rejection was a fail-safe or a deliberate verdict. If consensus logic ever changes to treat UNCERTAIN differently, this creates a security hole. |
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
| **Impact** | **Decision-integrity gap, not merely a feature gap.** The LLM is asked to render a SOVEREIGN TIER verdict on a packet containing only 4 fields. Without historical win rate, ML confidence, and RGI trust, the model cannot distinguish between a high-conviction signal and a noise signal. The verdict is structurally uninformed: the model has no basis to approve OR reject beyond surface-level price heuristics. This is not "missing enrichment" — it is an integrity violation because the system claims the verdict is evidence-based (per the system prompt: "Base every judgment solely on the trade signal fields provided") while withholding the evidence that would make the judgment sound. A verdict produced on incomplete evidence is not a valid verdict; it is a coin flip decorated with reasoning. |
| **Current Safeguard** | The RGI confidence arbiter (post-debate) provides some correction via trust_probability, but this happens AFTER the debate — the LLM never sees it. The post-hoc gate cannot compensate for a fundamentally uninformed verdict. |
| **Governance Fix** | Phase 6 C4 (DecisionPacketBuilder) will define which sovereign_intel fields are injected. C3 (ContextPriorityPolicy) will tier them. Key sovereign_intel fields (historical win rate, ML confidence, RGI trust indicator) will be classified as Tier 2 (IMPORTANT) — included when available but their absence does not block the decision. If the sovereign_intel layer is unreachable, the missing_data_flags section explicitly tells the LLM that intelligence is unavailable. |
| **Upgrade Rationale** | Reclassified from S2 to S1 because: (1) the system prompt mandates evidence-based judgment but the evidence is withheld, (2) a verdict on 4 fields alone cannot meet the "certainty is required for APPROVED" standard, (3) wiring sovereign_intel is a prerequisite for decision-packet integrity — without it, the packet is structurally incomplete regardless of how well the other subsystems work. |

---

#### FM-09: Pre-Trade Audit Completely Disconnected

| Attribute | Detail |
|-----------|--------|
| **Severity** | S3 — MODERATE |
| **Location** | `pre_trade_audit.py` — NEVER IMPORTED in `webhook.py` |
| **Current Behavior** | `pre_trade_audit.py` implements an adversarial audit using DeepSeek-R1 that generates 3 rejection reasons per signal. It is a completely separate decision path that is not wired into the hot path. |
| **Impact** | Wasted implementation. No adversarial challenge to the bull/bear consensus. |
| **Governance Fix** | Phase 6 will NOT wire pre_trade_audit into the hot path. Reason: it uses a DIFFERENT model (DeepSeek-R1) with separate token budgets, latency characteristics, and failure modes. Future Phase 7 candidate for offline batch audit. |

---

#### FM-10: No Prompt Versioning — v1.0.0 Hardcoded

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `ai_council_system_prompt.txt` line 1: `# SYSTEM PROMPT v1.0.0` |
| **Current Behavior** | The system prompt has a version comment (`v1.0.0`) but this is a human-readable comment, not a machine-tracked version. The prompt templates have NO version at all. If someone edits a prompt, there is no audit trail of what version produced which debate. |
| **Impact** | No prompt lineage. Cannot reproduce past decisions. Cannot A/B test prompt changes. |
| **Governance Fix** | Phase 6 C10 (PromptVersionRegistry) will hash every prompt version (SHA-256) and store the hash alongside each debate record. Prompt changes require version bump. Hash mismatch = REJECT. |

---

#### FM-11: No Model Fingerprinting — No Audit Trail of Model Identity

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | `ai_council.py` — model name stored nowhere in debate result |
| **Current Behavior** | `DebateResult` contains: correlation_id, bull_reasoning, bear_reasoning, bull_verdict, bear_verdict, consensus_score, final_verdict. It does NOT contain: which model produced the reasoning, model version/hash, quantization level (for Ollama). |
| **Impact** | Cannot attribute decisions to specific model versions. Cannot detect model drift. Cannot perform regression analysis across model changes. |
| **Governance Fix** | Phase 6 C11 (ModelFingerprintLogger) will record: model name, model version/tag, quantization level, Ollama model digest (SHA-256), and backend type (OPENROUTER/OLLAMA) in every debate record. |

---

#### FM-12: System Prompt Budget Uses Characters, Not Tokens

| Attribute | Detail |
|-----------|--------|
| **Severity** | S3 — MODERATE |
| **Location** | `ai_council.py` line ~134: `_SYSTEM_PROMPT_BUDGET: int = 512` |
| **Current Behavior** | `_load_system_prompt()` truncates at 512 CHARACTERS. But LLM context windows are measured in TOKENS. |
| **Governance Fix** | Phase 6 C6 (TokenBudgetGuard) will replace character-based budgets with token-based budgets using a deterministic estimation function. |

---

#### FM-13: `/no_think` Prefix in Prompt Templates

| Attribute | Detail |
|-----------|--------|
| **Severity** | S3 — MODERATE |
| **Location** | `ai_council.py` → `BULL_PROMPT_TEMPLATE` and `BEAR_PROMPT_TEMPLATE` |
| **Current Behavior** | Both templates start with `/no_think` — a Qwen3-specific instruction. This is correct for qwen3:8b but is meaningless noise for non-Qwen models on OpenRouter. |
| **Governance Fix** | Phase 6 C10 (PromptVersionRegistry) will support backend-specific prompt variants. The `/no_think` prefix will only be injected for Qwen-family models on Ollama. |

---

#### FM-14: Required-vs-Optional Context Not Explicitly Governed

| Attribute | Detail |
|-----------|--------|
| **Severity** | S1 — CRITICAL |
| **Location** | System-wide — no field criticality classification exists anywhere in the codebase |
| **Current Behavior** | The prompt templates inject exactly 4 signal fields. The context builder would add execution mode, guardian state, and last 3 debates. The sovereign intel layer would add RAG results, ML confidence, win rate, and RGI trust. But NOWHERE is any field classified as REQUIRED vs OPTIONAL vs NEVER. Every field is implicitly "include if available, skip if not." |
| **Impact** | Token budgeting (C6), overflow rejection (C7), and compact encoding (C5) all depend on field criticality. Without it, these subsystems cannot make deterministic decisions about what to include, what to drop, and when to REJECT. The governance layer collapses to "best effort" — violating Non-Negotiable #4. |
| **Governance Fix** | Phase 6 C2 (DECISION_PACKET_SPEC.md) defines every field with an explicit classification: REQUIRED (Tier 1), IMPORTANT (Tier 2), OPTIONAL (Tier 3), NEVER (Tier 4). C3 (ContextPriorityPolicy) enforces these tiers at construction time. C7 (OverflowRejectPolicy) uses them to determine whether to drop-and-log or REJECT-and-halt. |

---

#### FM-15: No Packet Hash / Context Checksum for Forensic Traceability

| Attribute | Detail |
|-----------|--------|
| **Severity** | S2 — SEVERE |
| **Location** | System-wide — no packet identity mechanism exists |
| **Current Behavior** | The debate result contains `correlation_id` and reasoning but the INPUT to the LLM — the exact prompt that was sent — is not hashed or checksummed. If the prompt templates change, if context is injected differently, or if a field is silently dropped, the audit trail has no way to detect this. |
| **Impact** | Incomplete audit lineage. Prompt versioning + model fingerprinting answer "what template?" and "what model?" but not "what exact input?" Regression testing cannot verify that a known packet hash produces a known verdict. |
| **Governance Fix** | Phase 6 C2 (DECISION_PACKET_SPEC.md) defines a `packet_hash` field: SHA-256 of the complete, assembled decision packet. This hash is stored alongside prompt_version_hash and model_fingerprint, completing the three-dimensional audit lineage: `(packet_hash × prompt_version × model_fingerprint) → verdict`. |

---

### 3.3 Unwired Components Summary

| Component | Location | Lines | Status | Phase 6 Action |
|-----------|----------|-------|--------|----------------|
| `ollama_context_builder.py` | `app/logic/` | 170 | FULLY IMPLEMENTED, never imported in webhook | Wire via DecisionPacketBuilder (C4). Failure = REJECT. |
| `sovereign_intel.py` | `app/logic/` | 450 | FULLY IMPLEMENTED, never imported in webhook | Wire T2 fields via DecisionPacketBuilder (C4). Failure = log + continue. |
| `pre_trade_audit.py` | `app/logic/` | ~300 | IMPLEMENTED, never imported in webhook | DO NOT WIRE in Phase 6. Future Phase 7 candidate. |

### 3.4 Safety Features Already Working (DO NOT BREAK)

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

> To be completed in C3+. Will contain:
>
> - Context Priority Policy tiers
> - Token Budget allocation table
> - Prompt construction pipeline diagram

---

## 5. Decision Packet Specification (C2 — COMPLETE)

**Delivered:** [`DOCS/DECISION_PACKET_SPEC.md`](DECISION_PACKET_SPEC.md)

Defines the complete Decision Packet schema (version `DPv1.2`) with:

- 9 sections (A–I) in fixed order
- Field-level tier classification (REQUIRED / IMPORTANT / OPTIONAL / NEVER)
- Bounded max sizes for every variable-size field
- Field provenance classification (source-of-truth / derived-summary / advisory-metric)
- Missing data flags and omission rules
- SHA-256 packet hash for forensic traceability
- Compact encoding rules optimized for qwen3:8b
- Token budget worksheet (2,048 Safe Operating Budget)
- 18 validation rules with error codes (DPB-001 through DPB-018)
- DPB-017 CROSS_LAYER_INCONSISTENCY — validates alignment across packet layers
- DPB-018 INSUFFICIENT_DECISION_CONTEXT — rejects informationally hollow packets
- LLM Interpretation Contract (§10) — explicit behavioral rules for missing data, advisory metrics, low-quality context, and contradiction signals
- Token Pressure Simulation requirement (§11) — 6 scenarios validating tier-based drop behavior
- Deterministic packet hash with audit trail linkage (§6.2–6.4)
- Versioning policy (major/minor/patch)

---

## 6. Context Priority Policy (C3 — COMPLETE)

**Delivered:** [`DOCS/CONTEXT_PRIORITY_POLICY.md`](CONTEXT_PRIORITY_POLICY.md)

Defines the deterministic tier enforcement policy (version `CPPv1.1`) with:

- 4 tiers: T1 (MUST-INCLUDE, 18 fields), T2 (SHOULD-INCLUDE, 6 fields, priority-ordered), T3 (MAY-INCLUDE, 2 fields), T4 (NEVER-INCLUDE, 8 prohibitions)
- 6 independent failure domains with isolation guarantees
- Deterministic field inclusion algorithm (8 phases)
- T2 priority ranking with rationale
- Resolution timeout policy (max 500ms total, concurrent resolution)
- Data quality grades (FULL / PARTIAL / MINIMAL) with LLM instruction semantics
- Overflow resolution sequence (T3 dropped first, then T2 in reverse priority)
- 21 policy invariants (expanded from 13 — includes hash determinism, audit linkage, validation ordering, interpretation contract, AM/SoT override prohibition)
- 28 validation test scenarios for golden regression suite (expanded from 16 — includes DPB-017/018 scenarios and token pressure simulation)
- LLM Interpretation Enforcement section (§9) — system prompt contract injection and verification
- Packet Hash Policy section (§10) — deterministic generation, logging mandate, audit trail linkage
- Subsystem interaction map (C4, C5, C6, C7, C10, C11)

---

## 7. Pre-C4 Gate Conditions

The following governance requirements were added after C2/C3 acceptance and
MUST be satisfied before C4 (DecisionPacketBuilder) implementation begins.

### 7.1 Validation Rules Gate

| Rule | Spec Reference | Status |
|------|---------------|--------|
| DPB-017 CROSS_LAYER_INCONSISTENCY | DPv1 §7.3 | SPECIFIED |
| DPB-018 INSUFFICIENT_DECISION_CONTEXT | DPv1 §7.4 | SPECIFIED |

### 7.2 Token Pressure Simulation Gate

| Requirement | Spec Reference | Status |
|-------------|---------------|--------|
| 6 simulation scenarios defined (TP-01 through TP-06) | DPv1 §11.2 | SPECIFIED |
| Validation criteria defined (7 criteria) | DPv1 §11.3 | SPECIFIED |
| Documentation format defined | DPv1 §11.4 | SPECIFIED |
| C4 acceptance gated on ALL 6 passing | DPv1 §11.4 | GATE ACTIVE |

### 7.3 LLM Interpretation Contract Gate

| Requirement | Spec Reference | Status |
|-------------|---------------|--------|
| MDF-NOINFER: no inference of missing fields | DPv1 §10.1 | SPECIFIED |
| MDF-NODEFAULT: no default substitution | DPv1 §10.1 | SPECIFIED |
| MDF-UNCERTAINTY: missing flags increase uncertainty | DPv1 §10.1 | SPECIFIED |
| AM-NOOVERRIDE: advisory cannot override SoT | DPv1 §10.2 | SPECIFIED |
| AM-CONFLICT: disagreement = uncertainty | DPv1 §10.2 | SPECIFIED |
| LQC-REDUCE: low quality reduces confidence | DPv1 §10.3 | SPECIFIED |
| CSR-FLAG/CSR-REJECT/CSR-REASONING: contradiction handling | DPv1 §10.4 | SPECIFIED |
| System prompt must encode all rules | CPPv1.1 §9 | SPECIFIED |

### 7.4 Packet Hash Governance Gate

| Requirement | Spec Reference | Status |
|-------------|---------------|--------|
| Deterministic hash generation | DPv1 §6.3 | SPECIFIED |
| Hash logged with every decision | DPv1 §6.2 rule 6 | SPECIFIED |
| Hash included in audit trail linkage | DPv1 §6.4 | SPECIFIED |
| Hash usable as regression test key | DPv1 §6.2 rule 8 | SPECIFIED |

> **Gate verdict:** All pre-C4 governance requirements are SPECIFIED.
> C4 implementation may proceed. C4 acceptance requires all gates to PASS.

---

## 8. Subsystem Specifications (Stub — C4 through C12)

### 8.1 DecisionPacketBuilder (C4)

**Status:** COMPLETE
**Implementation:** See [DECISION_PACKET_BUILDER_IMPLEMENTATION.md](DECISION_PACKET_BUILDER_IMPLEMENTATION.md)
**Test Results:** 70/70 passing

**Deliverables:**

| Module | Path | Purpose |
|--------|------|--------|
| decision_packet_models.py | app/logic/ | Input contracts, enums, error types, DecisionPacket dataclass |
| decision_packet_builder.py | app/logic/ | 8-phase deterministic pipeline (CPPv1.1 §2.1) |
| decision_packet_validator.py | app/logic/ | 18 DPB rules (DPB-001 through DPB-018) |
| decision_packet_serializer.py | app/logic/ | Canonical compact encoding, SHA-256 hash, token estimation |
| test_decision_packet_builder.py | tests/unit/ | 70 unit tests across 15 test classes |

**Key Properties:**

- All T1 fields REQUIRED — missing = REJECT
- T2 fields resolved in P1→P6 priority order; missing = flag + continue
- T3 fields included only if token budget allows; missing = silent omission
- Overflow resolution per CPPv1.1 §4.3 (drop T3 → T2 reverse priority)
- Zero-Float Mandate enforced at all `Decimal` input boundaries
- SHA-256 packet hash computed over canonical serialization of sections B-H
- Fail-closed: guardian locked → REJECT, float detected → REJECT, T1 missing → REJECT
- All 18 validation rules evaluated (full diagnostics, no short-circuit)

### 8.2 CompactFormatEncoder (C5)

### 8.3 TokenBudgetGuard (C6)

**Status:** COMPLETE
**Implementation:** `app/logic/token_budget_guard.py`
**Test Results:** 56/56 passing

**Deliverables:**

| Module | Path | Purpose |
|--------|------|--------|
| token_budget_guard.py | app/logic/ | Provider-aware token budget enforcement layer |
| test_token_budget_guard.py | tests/unit/ | 56 unit tests across 14 test classes |

**Budget Model:**

| Component | Tokens | Notes |
|-----------|--------|-------|
| Input Budget | 1,400 | Sections A–H combined |
| Output Reserve | 512 | Reserved for LLM response |
| Safety Margin | 136 | Headroom buffer |
| **Safe Operating Budget** | **2,048** | **Invariant: input + output + margin** |

**Per-Section Budgets (DPv1.2 §2.1, HDR corrected):**

| Section | Code | Budget |
|---------|------|--------|
| System Prompt | SYS | 200 |
| Packet Header | HDR | 60 (spec correction from 50 — real headers need 55+) |
| Signal Fields | SIG | 80 |
| Operational Context | OPS | 60 |
| History Summary | HST | 100 |
| Intelligence Layer | INT | 150 |
| Missing Data Flags | MDF | 60 |
| Verdict Instruction | VRD | 100 |

**Error Codes:**

| Code | Description |
|------|-------------|
| TBG-001 | Total input exceeds input budget |
| TBG-002 | System prompt exceeds SYS section budget |
| TBG-003 | Individual section exceeds its budget |
| TBG-004 | T1 fields alone exceed input budget (specification error) |
| TBG-005 | Silent truncation detected (T2 dropped without flag) |
| TBG-006 | Output reserve insufficient |

**Key Properties:**

- Provider-aware: supports LOCAL_OLLAMA (qwen3:8b) and OPENROUTER profiles
- Budget invariant validated at profile construction time
- Pre-build checks: system prompt budget, T1 budget pre-flight
- Post-build checks: full packet per-section breakdown, total input, silent truncation
- Zero-truncation mandate: exceeded budget → REJECT, never silently truncate
- Unknown model names fall back to qwen3:8b (most conservative)
- Independent of DecisionPacketBuilder — can be invoked before, during, or after
- HDR section budget corrected from 50→60 during testing: real headers with UUID + SHA-256 + model fingerprint require 55+ tokens

### 8.4 OverflowRejectPolicy (C7)

### 8.5 StrictOutputSchema (C8)

### 8.6 RejectOnAmbiguityPolicy (C9)

### 8.7 PromptVersionRegistry (C10)

### 8.8 ModelFingerprintLogger (C11)

### 8.9 DB-Aware Context Injection (C12)

> Each subsystem will be specified before implementation begins.

---

## 9. Integration Plan (Stub — C13)

> Integration with `ai_council.py`, `webhook.py`, `ollama_context_builder.py`.
> Must not break existing safety features (Section 3.4).

---

## 10. Golden Regression Suite (Stub — C13)

> Deterministic test vectors with known-good inputs → expected outputs.
> Will cover: packet construction, token budgeting, verdict parsing,
> ambiguity rejection, overflow rejection, prompt versioning.
> Must include DPB-017/DPB-018 scenarios and token pressure simulation vectors.

---

## 11. Validation Checklist (Stub — C14)

> 14 specific validation requirements from Phase 6 mandate.
> Plus: pre-C4 gate conditions (§7) must all show PASS.

---

## 12. Observability (Stub — C12)

> Metrics, structured logging, and dashboard requirements for the governance layer.
> Must include: packet_hash logging, DPB-017/DPB-018 rejection metrics,
> token pressure event counters, LLM interpretation contract violation alerts.

---

## 13. Runbook (Stub — C14)

> To be delivered as `DOCS/LLM_CONTEXT_RUNBOOK.md`.

---

## 14. Regression Test Plan (Stub — C13)

> To be delivered as `DOCS/LLM_REGRESSION_TEST_PLAN.md`.
> Must cover all 28 CPPv1.1 test scenarios and 6 token pressure simulation scenarios.

---

## 15. Change Log

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-03-29 | Kiro Agent | C1: Failure mode analysis (13 failure modes, 3 unwired components, 10 safety features) |
| 1.1.0 | 2026-03-29 | Kiro Agent | C1 amendments: FM-08 reclassified S2→S1 (decision-integrity gap), FM-14 added (field criticality ungoverned, S1), FM-15 added (no packet hash, S2). Priority matrix updated. Total: 15 failure modes. |
| 1.2.0 | 2026-03-29 | Kiro Agent | C2: Decision Packet Specification delivered (DECISION_PACKET_SPEC.md). DPv1 schema with field tiers, SHA-256 hashability, compact encoding, token budget worksheet. |
| 1.3.0 | 2026-03-29 | Kiro Agent | C2 refinements: recent_debates downgraded to T2 (replaced with bounded T1 history_summary), per-field bounds added, field provenance classification added, DPB-016 INTERNAL_PACKET_CONTRADICTION added, Safe Operating Budget philosophy stated. |
| 1.4.0 | 2026-03-29 | Kiro Agent | C3: Context Priority Policy delivered (CONTEXT_PRIORITY_POLICY.md). CPPv1.0 with 4 tiers, 6 failure domains, 13 invariants, 16 test scenarios. |
| 1.5.0 | 2026-03-29 | Kiro Agent | **Pre-C4 governance amendments:** DPB-017 CROSS_LAYER_INCONSISTENCY and DPB-018 INSUFFICIENT_DECISION_CONTEXT validation rules added to DPv1.2. Token Pressure Simulation requirement added (6 scenarios, 7 validation criteria, documentation gate). LLM Interpretation Contract added (MDF-NOINFER, MDF-NODEFAULT, MDF-UNCERTAINTY, AM-NOOVERRIDE, AM-CONFLICT, LQC-REDUCE, CSR rules). Packet hash governance expanded (deterministic generation, per-decision logging, audit trail linkage, regression test key). CPPv1.1 updated with 21 invariants (from 13), 28 test scenarios (from 16), interpretation enforcement section, packet hash policy section. Pre-C4 gate conditions defined (§7). Total validation rules: 18 (DPB-001 through DPB-018). |
| 1.6.0 | 2026-03-29 | Kiro Agent | **C6: TokenBudgetGuard** delivered. 56/56 tests passing. Token budget enforcement module with ceil-based estimation, section-level budgets, overflow rejection policy. |
| 1.7.0 | 2026-03-30 | Kiro Agent | **Phase 7: AI Backend Reliability Manager** delivered. `app/logic/ai_backend_reliability.py` (~600 lines) with 5 provider modes, 13 failure classes, cooldown-based health tracking, deterministic routing ladder, fail-closed guarantee. 56/56 tests passing. Webhook integrated. Documentation: AI_BACKEND_RELIABILITY_PLAN.md, AI_PROVIDER_POLICY.md, AI_BACKEND_FAILURE_CODES.md, AI_BACKEND_RUNBOOK.md. |

---

## 16. Final Verdict (Stub — C15)

> Must return exactly one of:
>
> - `PHASE 6 COMPLETE`
> - `PHASE 6 PARTIAL`
> - `PHASE 6 BLOCKED`

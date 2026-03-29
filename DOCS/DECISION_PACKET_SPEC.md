# Decision Packet Specification

## Project Autonomous Alpha — Phase 6, Sub-Phase C2

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Spec Version:** 1.1.0
**Packet Schema Version:** `DPv1`
**Status:** LOCKED (C2 refinements applied)
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2026-03-29

---

## 1. Purpose

This document defines the **Decision Packet** — the exact, deterministic data structure that is assembled from system state, serialized to a compact text format, budget-checked against the model's token capacity, hashed for forensic traceability, and submitted to the LLM as the sole input for the Bull/Bear debate.

**The LLM sees ONLY the Decision Packet. Nothing else enters the prompt.**

### 1.1 Design Principles

| # | Principle | Enforcement |
|---|-----------|-------------|
| 1 | Every field has an explicit classification (REQUIRED / IMPORTANT / OPTIONAL / NEVER) | ContextPriorityPolicy (C3) |
| 2 | Every field has a bounded maximum size | CompactFormatEncoder (C5) |
| 3 | REQUIRED field missing = trade REJECTED (no LLM call) | OverflowRejectPolicy (C7) |
| 4 | Total packet must fit within token budget | TokenBudgetGuard (C6) |
| 5 | If budget exceeded after including all REQUIRED fields, REJECT (never truncate) | OverflowRejectPolicy (C7) |
| 6 | Packet is hashed (SHA-256) before LLM submission | DecisionPacketBuilder (C4) |
| 7 | Packet hash stored alongside debate record for forensic replay | ModelFingerprintLogger (C11) |
| 8 | Compact enough for qwen3:8b (32K context, but our budget is much smaller) | CompactFormatEncoder (C5) |
| 9 | No emoji, no decorative formatting, no Markdown in prompt payload | CompactFormatEncoder (C5) |
| 10 | All numeric values rendered as strings (Zero-Float Mandate) | DecisionPacketBuilder (C4) |

### 1.2 Target Model Constraints

| Property | Value | Source |
|----------|-------|--------|
| Primary model | qwen3:8b | `OLLAMA_MODEL` env var |
| Context window | 32,768 tokens | Qwen3 spec |
| **Safe Operating Budget** | **2,048 tokens** | **See §1.3 below** |
| System prompt budget | 200 tokens | Tier 1 allocation |
| Decision packet budget | 1,200 tokens | Tier 1 + Tier 2 allocation |
| Output reserve | 512 tokens | `num_predict` in Ollama config |
| Safety margin | 136 tokens | Buffer for tokenizer variance |
| Token estimation | 1 token ≈ 3.5 chars (Qwen) | Empirical; confirmed for English + numbers |

### 1.3 Budget Philosophy

**2,048 tokens is the SAFE OPERATING BUDGET — not the maximum theoretical model window.**

The system intentionally uses < 7% of qwen3:8b's 32K context window. This is by design:

1. **Reliability over capacity.** A smaller, tightly bounded packet is deterministic. A large context window invites uncontrolled growth, silent truncation, and unpredictable model attention distribution. We optimize for verdict reliability, not information throughput.
2. **Tokenizer variance.** Character-to-token ratios vary by content (numbers, special characters, mixed case). A 16× headroom factor absorbs these differences without risking overflow.
3. **Model attention quality.** Smaller prompts receive higher per-token attention from the model. Financial verdicts require concentrated analysis, not broad summarization.
4. **Future-proofing.** If the system migrates to a smaller model (e.g., 4K context), the 2,048 budget still fits. The budget is model-portable.
5. **Fail-closed guarantee.** At 2,048 tokens, the OverflowRejectPolicy can confidently REJECT on budget violation. At 32K, "over budget" becomes subjective.

---

## 2. Packet Structure Overview

The Decision Packet has a fixed section order. Sections are NEVER reordered — the model sees them in the same sequence every time, providing structural consistency for verdict stability.

```
┌─────────────────────────────────────────────────┐
│ SECTION A: Packet Header (metadata, version)    │  ← Always first
├─────────────────────────────────────────────────┤
│ SECTION B: Signal Summary (the trade signal)    │  ← REQUIRED
├─────────────────────────────────────────────────┤
│ SECTION C: Risk Summary (position sizing)       │  ← REQUIRED
├─────────────────────────────────────────────────┤
│ SECTION D: Execution Context (system state)     │  ← REQUIRED
├─────────────────────────────────────────────────┤
│ SECTION E: Historical Context (recent debates)  │  ← REQUIRED
├─────────────────────────────────────────────────┤
│ SECTION F: Intelligence Briefing (ML/RGI)       │  ← IMPORTANT
├─────────────────────────────────────────────────┤
│ SECTION G: Missing Data Flags                   │  ← REQUIRED
├─────────────────────────────────────────────────┤
│ SECTION H: Task Instruction                     │  ← REQUIRED
├─────────────────────────────────────────────────┤
│ SECTION I: Required Output Schema               │  ← REQUIRED
└─────────────────────────────────────────────────┘
```

---

## 3. Field Classification Tiers

Every field in the packet is classified under exactly one tier. No field exists without classification — that would violate FM-14.

| Tier | Label | Rule | On Missing |
|------|-------|------|------------|
| **T1** | REQUIRED | Must be present in every packet. Omission = REJECT before LLM call. | `REJECT: T1 field [{field_name}] missing` — no LLM call made |
| **T2** | IMPORTANT | Include if token budget allows after all T1 fields. Log if omitted. | `WARN: T2 field [{field_name}] omitted (budget={remaining} tokens)` — proceed with LLM call |
| **T3** | OPTIONAL | Include only if surplus budget after T1 + T2. Silent omit is acceptable. | Silently omitted. No log unless debug mode. |
| **T4** | NEVER | Explicitly forbidden from entering the packet. Presence = build error. | Build error: `FATAL: T4 field [{field_name}] found in packet` |

### 3.1 Tier Allocation Budget

| Tier | Max Token Allocation | Notes |
|------|---------------------|-------|
| T1 (REQUIRED) | 700 tokens | Signal + risk + execution + history + flags + task + output schema |
| T2 (IMPORTANT) | 400 tokens | Intelligence briefing (ML, RGI, win rate) |
| T3 (OPTIONAL) | 100 tokens | Additional similar debates, extended reasoning |
| **Total packet** | **1,200 tokens** | Leaves 200 (system prompt) + 512 (output) + 136 (margin) |

If T1 fields alone exceed 700 tokens, the packet is malformed → REJECT.
If T1 + T2 fields exceed 1,100 tokens, T2 fields are dropped in reverse priority order (lowest T2 field dropped first). If T1 + minimum T2 still exceed 1,200 tokens → REJECT.

---

## 4. Field Catalog

### 4.1 SECTION A — Packet Header

| Field | Type | Tier | Max Size | Format | Source | Description |
|-------|------|------|----------|--------|--------|-------------|
| `packet_version` | string | T1 | 8 chars | `DPv1` | Hardcoded | Schema version tag. Changes require migration. |
| `packet_hash` | string | T1 | 64 chars | SHA-256 hex | Computed | Hash of the complete packet (all sections B-I concatenated in canonical order). Populated AFTER assembly, BEFORE LLM call. NOT included in the prompt sent to the LLM — stored in audit record only. |
| `correlation_id` | string | T1 | 36 chars | UUID v4 | `webhook.py` | Links packet to originating signal. |
| `timestamp_utc` | string | T1 | 20 chars | `YYYY-MM-DDTHH:MM:SSZ` | System clock | Packet assembly time. |

**Header rendering (compact):**
```
[DPv1|{correlation_id}|{timestamp_utc}]
```
**Estimated tokens:** ~25

**Note on `packet_hash`:** The hash is computed from sections B through I after assembly. It is NOT included in the rendered prompt (that would create a circular dependency). It IS stored in the `ai_debates` record alongside `prompt_version_hash` and `model_fingerprint`. This completes the three-dimensional audit lineage: `(packet_hash × prompt_version × model_fingerprint) → verdict`.

---

### 4.2 SECTION B — Signal Summary

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `symbol` | string | T1 | 20 chars | `^[A-Z0-9]+$` | `SignalIn.symbol` | Trading pair (e.g., BTCZAR) |
| `side` | string | T1 | 4 chars | `BUY` \| `SELL` | `SignalIn.side` | Trade direction |
| `price` | string | T1 | 32 chars | Decimal string, `> 0` | `SignalIn.price` | Signal price in ZAR. Rendered as `str(Decimal)`. |
| `signal_quantity` | string | T1 | 32 chars | Decimal string, `> 0` | `SignalIn.quantity` | Raw signal quantity from TradingView. |

**Section rendering (compact):**
```
SIGNAL: {symbol} {side} @ {price} ZAR qty={signal_quantity}
```
**Estimated tokens:** ~20

---

### 4.3 SECTION C — Risk Summary

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `position_size` | string | T1 | 32 chars | Decimal string, `> 0` | `RiskProfile.calculated_quantity` | Risk-managed position size. |
| `risk_pct` | string | T1 | 8 chars | Decimal string, `0 < x ≤ 1` | `RiskProfile.risk_percentage` | Risk as decimal fraction (0.01 = 1%). |
| `risk_zar` | string | T1 | 32 chars | Decimal string, `> 0` | `RiskProfile.risk_amount_zar` | Absolute risk amount in ZAR. |
| `equity_zar` | string | T1 | 32 chars | Decimal string, `> 0` | `RiskProfile.equity` | Account equity at decision time. |

**Section rendering (compact):**
```
RISK: pos={position_size} risk={risk_pct} risk_zar={risk_zar} equity={equity_zar}
```
**Estimated tokens:** ~25

---

### 4.4 SECTION D — Execution Context

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `execution_mode` | string | T1 | 12 chars | `PAPER` \| `LIVE` \| `DEMO` \| `UNKNOWN` | `EXECUTION_MODE` env var | Current trading mode. |
| `guardian_state` | string | T1 | 10 chars | `LOCKED` \| `UNLOCKED` \| `UNKNOWN` | Guardian lock file | Guardian circuit breaker state. |
| `demo_mode` | string | T3 | 5 chars | `true` \| `false` \| `UNKNOWN` | `DEMO_MODE` env var | Demo flag (redundant with execution_mode for most cases). |

**Section rendering (compact):**
```
EXEC: mode={execution_mode} guardian={guardian_state}
```
**Estimated tokens:** ~12

**Omission rule:** If `execution_mode` is `UNKNOWN`, log warning but proceed. If `guardian_state` is `LOCKED`, the debate may still proceed (Guardian is an independent gate — the LLM should KNOW the system is locked so it can factor this into its analysis, but the Guardian gate independently prevents execution). If `guardian_state` retrieval fails entirely (exception), set to `UNKNOWN` and log `FM-03-GUARDIAN-FAIL`.

---

### 4.5 SECTION E — Historical Context

This section provides a **bounded summary** of recent debate history for the same symbol. It is classified as **T2 (IMPORTANT)**, not T1, because:

1. On a fresh system there IS no history — making this T1 would REJECT the very first trade.
2. History is a derived summary, not a source-of-truth signal field. The trade decision should be possible (though less informed) without it.
3. A variable-length array in the T1 hot path creates unbounded token consumption risk. The bounded summary field eliminates this.

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `history_summary` | string | T2 | 80 chars | Bounded summary | `ollama_context_builder._get_recent_debates()` | Pre-computed one-line summary of last 3 same-symbol debates. |

The `history_summary` field replaces the previous `recent_debates[]` array. Instead of injecting a variable-length array into the prompt, the DecisionPacketBuilder pre-computes a fixed-format summary string.

**Summary format (deterministic, max 80 chars):**
```
{n} debates: {approved_count}A/{rejected_count}R last={verdict} score={score}
```

**Examples:**
```
3 debates: 1A/2R last=REJECTED score=50
0 debates: no history
DB unavailable
```

**Section rendering (compact):**
```
HISTORY ({symbol}): {history_summary}
```
**Estimated tokens:** ~15

**Omission rules:**
- If DB query succeeds with results: summary is computed from up to 3 most recent debates.
- If DB query succeeds with zero results: `history_summary` = `0 debates: no history`.
- If DB query fails: `history_summary` = `DB unavailable`. A `missing_data_flags` entry is added: `history_unavailable=true`.
- As a T2 field, if token budget is exceeded, the entire section is dropped and flagged in Section G. This is safe — the LLM is told via `missing_data_flags` that history is absent.

---

### 4.6 SECTION F — Intelligence Briefing

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `historical_win_rate` | string | T2 | 6 chars | `0.0`–`100.0` | `PredictiveContext.historical_win_rate` | Win rate for this symbol (%). |
| `total_similar_trades` | string | T2 | 6 chars | Integer string ≥ 0 | `PredictiveContext.historical_total_trades` | Count of similar historical trades. |
| `symbol_bias` | string | T2 | 8 chars | `BULLISH` \| `BEARISH` \| `NEUTRAL` | `PredictiveContext.symbol_bias` | Historical directional bias. |
| `ml_confidence` | string | T2 | 6 chars | `0.0`–`100.0` | `PredictiveContext.ml_confidence_score` | ML prediction confidence. |
| `ml_action` | string | T2 | 8 chars | `BUY` \| `SELL` \| `NEUTRAL` \| `HOLD` | `PredictiveContext.ml_recommended_action` | ML recommended action. |
| `rgi_trust` | string | T2 | 6 chars | `0.0`–`100.0` | `PredictiveContext.rgi_trust_probability × 100` | RGI trust as percentage. |
| `rgi_status` | string | T2 | 12 chars | `AVAILABLE` \| `UNAVAILABLE` | `PredictiveContext.rgi_available` | Whether RGI was queryable. |
| `ml_reasoning` | string | T3 | 120 chars | Free text, sanitized | `PredictiveContext.ml_reasoning` | ML reasoning (truncated). |
| `similar_debates` | array[object] | T3 | 3 entries max | See sub-fields | `PredictiveContext.similar_debates` | RAG-retrieved similar debates. |
| `similar_debates[].price` | string | T3 | 32 chars | Decimal string | `SimilarDebate.price` | Historical trade price. |
| `similar_debates[].verdict` | string | T3 | 8 chars | `APPROVED` \| `REJECTED` | `SimilarDebate.verdict` | Historical verdict. |
| `similar_debates[].outcome` | string | T3 | 8 chars | `WIN` \| `LOSS` \| `PENDING` | `SimilarDebate.outcome` | Trade outcome if known. |

**Section rendering (compact) — T2 fields:**
```
INTEL: win_rate={historical_win_rate}% trades={total_similar_trades} bias={symbol_bias}
  ml: conf={ml_confidence} action={ml_action}
  rgi: trust={rgi_trust}% status={rgi_status}
```
**Estimated tokens:** ~35

**Section rendering — T3 fields (if budget allows):**
```
  ml_reason: {ml_reasoning}
  similar: {price} {verdict} {outcome} | {price} {verdict} {outcome} | ...
```
**Estimated tokens:** ~40 (additional)

**Omission rules:**
- If `sovereign_intel` is unreachable, ALL T2 fields in this section are omitted. A `missing_data_flags` entry is added: `intel_unavailable=true`. The packet proceeds to LLM — sovereign intel failure is NOT a REJECT condition (per FM-08 governance fix). However, the `missing_data_flags` section explicitly tells the LLM that intelligence is unavailable.
- If individual fields fail (e.g., ML is available but RGI is not), available fields are included and unavailable fields are rendered as `N/A`.
- T3 fields are dropped first if budget is tight. T2 fields are dropped in reverse order (`rgi_status` → `ml_action` → `ml_confidence` → `symbol_bias` → `total_similar_trades` → `historical_win_rate`). `historical_win_rate` is the last T2 field dropped.

---

### 4.7 SECTION G — Missing Data Flags

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `missing_data_flags` | object | T1 | 200 chars | Key-value pairs | Computed during assembly | Explicit flags for any data that could not be retrieved. |

**Possible flags:**

| Flag Key | Type | Condition |
|----------|------|-----------|
| `history_unavailable` | bool | DB query for recent debates failed |
| `intel_unavailable` | bool | sovereign_intel layer entirely unreachable |
| `ml_unavailable` | bool | ML prediction service unreachable |
| `rgi_unavailable` | bool | RGI Reward Governor unreachable |
| `guardian_unknown` | bool | Guardian lock file could not be read |
| `equity_stale` | bool | Equity value is from cache, not live |

**Section rendering (compact):**
```
MISSING: none
```
or
```
MISSING: history_unavailable=true, intel_unavailable=true
```
**Estimated tokens:** ~8 (none) to ~25 (multiple flags)

**Design rationale:** The LLM must NEVER be left to guess what data is missing. If context was unavailable, the model must be explicitly told. This transforms implicit omission into explicit declaration — the model can then apply the system prompt rule: "If any required signal field is absent or implausible, treat it as a critical risk and REJECT."

---

### 4.8 SECTION H — Task Instruction

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `task_instruction` | string | T1 | 300 chars | Fixed text, role-specific | PromptVersionRegistry (C10) | Per-role analysis instruction (BULL or BEAR). |
| `role` | string | T1 | 4 chars | `BULL` \| `BEAR` | Caller | Which perspective this packet is for. |

**Section rendering — BULL variant (compact):**
```
TASK [BULL]: Evaluate risk/reward merit. Cite only verifiable logic from fields above. Absent data = risk flag. Ambiguity = REJECTED. Respond with JSON only.
```

**Section rendering — BEAR variant (compact):**
```
TASK [BEAR]: Identify every material risk for capital loss. Cite only verifiable logic from fields above. Absent data = risk flag. Ambiguity = REJECTED. Respond with JSON only.
```
**Estimated tokens:** ~40

**Note:** The task instruction is role-specific but structurally identical. The only difference is the analytical perspective (risk/reward merit vs. capital loss risk). Both end with the JSON output mandate.

---

### 4.9 SECTION I — Required Output Schema

| Field | Type | Tier | Max Size | Allowed Values | Source | Description |
|-------|------|------|----------|----------------|--------|-------------|
| `output_schema` | string | T1 | 200 chars | Fixed JSON schema instruction | Hardcoded | Exact output format the model must follow. |

**Section rendering (compact):**
```
OUTPUT (strict JSON, no other text):
{"verdict":"APPROVED","reasoning":"..."}
or
{"verdict":"REJECTED","reasoning":"..."}
```
**Estimated tokens:** ~30

**Enforcement:** StrictOutputSchema (C8) will parse the model response as JSON. If parsing fails, RejectOnAmbiguityPolicy (C9) returns `REJECTED`. The `reasoning` field is limited to 500 characters in the output parser — any excess is truncated for storage but does not affect the verdict extraction.

---

### 4.10 TIER 4 — NEVER Fields (Explicitly Forbidden)

These fields MUST NEVER appear in the Decision Packet under ANY circumstances. Their presence in the packet is a build error that halts construction.

| Field | Reason for Exclusion |
|-------|---------------------|
| `api_key` / `auth_token` | Credential leakage risk |
| `raw_webhook_body` | Unvalidated external input; injection risk |
| `user_email` / `operator_name` | PII; no relevance to trade decision |
| `database_connection_string` | Infrastructure secret |
| `system_prompt_text` | Already injected via system message; duplication wastes tokens and creates conflicting instructions |
| `previous_verdicts_reasoning` | Full reasoning text from prior debates; too large, uncontrolled size. Use structured `recent_debates[]` summary instead. |
| `raw_ml_response` | Unstructured ML API response; must be extracted to typed fields |
| `float_values` | Any Python `float` type. All numeric values must be `str(Decimal)`. |
| `emoji` | Wastes tokens, inconsistent across tokenizers, no informational value |
| `markdown_formatting` | `#`, `**`, `---`, etc. Wastes tokens, model may interpret as structure |

---

## 4.11 Field Bounds Summary

Every variable-size field has an explicit maximum. This table aggregates all bounds for quick reference and enforcement by the DecisionPacketBuilder (C4).

**String Fields:**

| Field | Tier | Max Length | Enforcement |
|-------|------|-----------|-------------|
| `packet_version` | T1 | 8 chars | Hardcoded; reject if mismatch |
| `correlation_id` | T1 | 36 chars | UUID format; reject if malformed |
| `timestamp_utc` | T1 | 20 chars | ISO 8601; reject if malformed |
| `symbol` | T1 | 20 chars | Regex `^[A-Z0-9]+$`; reject if over |
| `side` | T1 | 4 chars | Enum {BUY, SELL}; reject if invalid |
| `price` | T1 | 32 chars | Decimal string; reject if over |
| `signal_quantity` | T1 | 32 chars | Decimal string; reject if over |
| `position_size` | T1 | 32 chars | Decimal string; reject if over |
| `risk_pct` | T1 | 8 chars | Decimal string; reject if over |
| `risk_zar` | T1 | 32 chars | Decimal string; reject if over |
| `equity_zar` | T1 | 32 chars | Decimal string; reject if over |
| `execution_mode` | T1 | 12 chars | Enum {PAPER, LIVE, DEMO, UNKNOWN} |
| `guardian_state` | T1 | 10 chars | Enum {LOCKED, UNLOCKED, UNKNOWN} |
| `demo_mode` | T3 | 5 chars | Enum {true, false, UNKNOWN} |
| `history_summary` | T2 | 80 chars | Pre-computed; truncate + `[…]` if over |
| `historical_win_rate` | T2 | 6 chars | Decimal string 0.0–100.0 |
| `total_similar_trades` | T2 | 6 chars | Integer string ≥ 0 |
| `symbol_bias` | T2 | 8 chars | Enum {BULLISH, BEARISH, NEUTRAL} |
| `ml_confidence` | T2 | 6 chars | Decimal string 0.0–100.0 |
| `ml_action` | T2 | 8 chars | Enum {BUY, SELL, NEUTRAL, HOLD} |
| `rgi_trust` | T2 | 6 chars | Decimal string 0.0–100.0 |
| `rgi_status` | T2 | 12 chars | Enum {AVAILABLE, UNAVAILABLE} |
| `ml_reasoning` | T3 | 120 chars | Free text; hard truncate + `[…]` |
| `task_instruction` | T1 | 300 chars | Fixed template text |
| `role` | T1 | 4 chars | Enum {BULL, BEAR} |
| `output_schema` | T1 | 200 chars | Fixed schema text |

**Array Fields:**

| Field | Tier | Max Cardinality | Entry Max Size | Enforcement |
|-------|------|----------------|---------------|-------------|
| `similar_debates[]` | T3 | 3 entries | 48 chars/entry | Truncate to 3; drop if budget tight |

**Composite Fields:**

| Field | Tier | Max Keys | Max Rendered Size | Enforcement |
|-------|------|---------|-------------------|-------------|
| `missing_data_flags` | T1 | 6 flags max | 200 chars | Fixed flag set; reject if unknown flag |

**Invariants:**
- No string field may exceed its max length after encoding. T1 over-length = REJECT. T2/T3 over-length = truncate + `[…]`.
- No array field may exceed its max cardinality. Excess entries are silently dropped (oldest first).
- `missing_data_flags` has a closed flag set (6 defined flags). Unknown flags are rejected as a build error.

---

## 4.12 Field Provenance Classification

Every field is classified by its provenance — how the value originates and what level of authority it carries. This is critical for understanding which fields represent ground truth vs. derived heuristics.

| Provenance | Definition | Trust Level |
|------------|-----------|-------------|
| **SOURCE-OF-TRUTH** | Originates directly from a validated system input (signal, risk engine, environment). Cannot be wrong if the source system is correct. | Highest — the LLM should treat these as facts. |
| **DERIVED-SUMMARY** | Computed from source-of-truth data via deterministic aggregation (counting, averaging). Accurate if the underlying query is correct, but represents a lossy compression of the original data. | High — accurate but incomplete. |
| **ADVISORY-METRIC** | Produced by a probabilistic model (ML, RGI) or heuristic. Represents a best-estimate prediction, not a fact. Can be wrong. The LLM should weight these as inputs, not axioms. | Medium — informative but fallible. The LLM must not treat advisory metrics as certainties. |

**Per-Field Classification:**

| Field | Provenance | Rationale |
|-------|-----------|----------|
| `symbol` | SOURCE-OF-TRUTH | Direct from validated TradingView signal |
| `side` | SOURCE-OF-TRUTH | Direct from validated TradingView signal |
| `price` | SOURCE-OF-TRUTH | Direct from validated TradingView signal |
| `signal_quantity` | SOURCE-OF-TRUTH | Direct from validated TradingView signal |
| `position_size` | SOURCE-OF-TRUTH | Output of deterministic risk engine |
| `risk_pct` | SOURCE-OF-TRUTH | Configuration value from risk engine |
| `risk_zar` | SOURCE-OF-TRUTH | Deterministic calculation: `equity × risk_pct` |
| `equity_zar` | SOURCE-OF-TRUTH | Account equity from exchange API / env config |
| `execution_mode` | SOURCE-OF-TRUTH | Environment variable, set by operator |
| `guardian_state` | SOURCE-OF-TRUTH | Lock file state, set by Guardian subsystem |
| `history_summary` | DERIVED-SUMMARY | Aggregated from `ai_debates` table (count, A/R ratio, last verdict). Lossy compression of full debate history. |
| `historical_win_rate` | DERIVED-SUMMARY | Computed from RAG-retrieved trade outcomes. Accurate for the sample queried, but sample may not be representative. |
| `total_similar_trades` | DERIVED-SUMMARY | Count of RAG-retrieved similar trades. Depends on RAG query quality. |
| `symbol_bias` | DERIVED-SUMMARY | Derived from `historical_win_rate` via threshold rules (≥60% = BULLISH, ≤40% = BEARISH, else NEUTRAL). Deterministic derivation but inherits upstream uncertainty. |
| `ml_confidence` | ADVISORY-METRIC | ML model prediction confidence. Probabilistic output from RLHF model. Can drift, can be overconfident, can be stale. The LLM should factor it in but not treat it as a fact. |
| `ml_action` | ADVISORY-METRIC | ML model recommended action. Same caveats as `ml_confidence`. |
| `rgi_trust` | ADVISORY-METRIC | Reward Governor learned trust probability. Based on historical WIN/LOSS patterns. Adapts over time but can be biased by limited training data. Not a guarantee. |
| `rgi_status` | SOURCE-OF-TRUTH | Binary availability check of the RGI subsystem. Either it responded or it didn't. |
| `ml_reasoning` | ADVISORY-METRIC | Free-text ML reasoning. Unverifiable by the LLM; provided for operator audit, not model reliance. |
| `missing_data_flags` | SOURCE-OF-TRUTH | Binary flags set by the DecisionPacketBuilder based on retrieval outcomes. Cannot be wrong. |

---

## 5. Compact Encoding Rules

The encoder transforms typed field values into a minimal text representation optimized for token efficiency with qwen3:8b.

### 5.1 Encoding Principles

| # | Rule | Example |
|---|------|---------|
| 1 | No JSON in the packet body (JSON is for output schema only) | `SIGNAL: BTCZAR BUY @ 1500000 ZAR` not `{"signal": {"symbol": "BTCZAR"}}` |
| 2 | Key-value pairs use `=` separator, no spaces around `=` | `risk=0.01` not `risk = 0.01` |
| 3 | Sections delimited by newlines, not horizontal rules | `\n` not `---` |
| 4 | Section labels are UPPERCASE, colon-terminated | `SIGNAL:` not `Signal:` or `## Signal` |
| 5 | Lists use numbered prefix, 2-space indent | `  1. ...` not `  - ...` |
| 6 | Decimal values rendered without trailing zeros | `1500000` not `1500000.0000000000` |
| 7 | Booleans rendered as `true` / `false` (lowercase) | `history_unavailable=true` |
| 8 | Absent T2/T3 values rendered as `N/A` | `ml_confidence=N/A` |
| 9 | Max field value length enforced by truncation + `[…]` suffix | `ml_reason=Market conditions suggest[…]` |
| 10 | No blank lines between fields within a section | Saves 1 token per blank line |

### 5.2 Full Packet Example (BULL Role)

```
[DPv1|a1b2c3d4-e5f6-7890-abcd-ef1234567890|2026-03-29T14:30:00Z]
SIGNAL: BTCZAR BUY @ 1500000 ZAR qty=0.001
RISK: pos=0.00095 risk=0.01 risk_zar=1500 equity=150000
EXEC: mode=PAPER guardian=UNLOCKED
HISTORY (BTCZAR, last 3):
  1. 2026-03-29 REJECTED score=50
  2. 2026-03-28 REJECTED score=0
  3. 2026-03-27 APPROVED score=100
INTEL: win_rate=33.3% trades=3 bias=BEARISH
  ml: conf=42.5 action=NEUTRAL
  rgi: trust=65.0% status=AVAILABLE
MISSING: none
TASK [BULL]: Evaluate risk/reward merit. Cite only verifiable logic from fields above. Absent data = risk flag. Ambiguity = REJECTED. Respond with JSON only.
OUTPUT (strict JSON, no other text):
{"verdict":"APPROVED","reasoning":"..."}
or
{"verdict":"REJECTED","reasoning":"..."}
```

**Character count:** ~620 characters
**Estimated tokens:** ~180 (well within 1,200 budget)

### 5.3 Full Packet Example (Degraded — Intel Unavailable)

```
[DPv1|a1b2c3d4-e5f6-7890-abcd-ef1234567890|2026-03-29T14:30:00Z]
SIGNAL: BTCZAR BUY @ 1500000 ZAR qty=0.001
RISK: pos=0.00095 risk=0.01 risk_zar=1500 equity=150000
EXEC: mode=PAPER guardian=UNLOCKED
HISTORY (BTCZAR): none on record
MISSING: intel_unavailable=true, history_unavailable=false
TASK [BEAR]: Identify every material risk for capital loss. Cite only verifiable logic from fields above. Absent data = risk flag. Ambiguity = REJECTED. Respond with JSON only.
OUTPUT (strict JSON, no other text):
{"verdict":"APPROVED","reasoning":"..."}
or
{"verdict":"REJECTED","reasoning":"..."}
```

**Character count:** ~510 characters
**Estimated tokens:** ~145

---

## 6. Packet Hashability Design

### 6.1 Hash Computation

The `packet_hash` provides forensic identity for every decision packet.

**Algorithm:** SHA-256
**Input:** Canonical byte representation of sections B through I, concatenated in section order, encoded as UTF-8.
**Output:** 64-character lowercase hex string.

### 6.2 Canonical Form

To ensure deterministic hashing regardless of construction order:

1. Sections are concatenated in fixed order: B, C, D, E, F, G, H, I
2. Each section is separated by a single `\n`
3. No trailing whitespace on any line
4. No trailing newline after the last section
5. All field values are normalized:
   - Decimal strings: no trailing zeros (use `Decimal.normalize()`)
   - Dates: always `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`
   - Enums: always UPPERCASE
   - Booleans: always lowercase `true` / `false`
6. Missing T2/T3 fields are EXCLUDED from the hash (they are non-deterministic based on budget)
7. Missing T1 fields cause REJECT before hash computation (hash never computed for invalid packets)

### 6.3 Hash Storage

```
ai_debates record:
  correlation_id  → links to signal
  packet_hash     → SHA-256 of decision packet (sections B-I)
  prompt_version  → SHA-256 of system prompt + task template
  model_fingerprint → model name + version + backend
  bull_reasoning  → model output (BULL)
  bear_reasoning  → model output (BEAR)
  final_verdict   → consensus result
```

**Three-dimensional audit lineage:**
```
(packet_hash × prompt_version × model_fingerprint) → verdict
```

Any change to ANY of these three dimensions produces a different hash tuple, making it detectable in regression testing.

### 6.4 Hash in Regression Testing

The GoldenDecisionRegressionSuite (C13) will use packet hashes as test vector identifiers:
- A golden test vector defines: input fields → expected packet_hash → expected compact rendering
- If the packet builder produces a different hash for the same inputs, a regression has occurred
- Hash stability proves the packet builder is deterministic

---

## 7. Missing Data Policy

### 7.1 Decision Matrix

| Data Source | Retrieval Fails | Effect on Packet | Effect on Trade |
|-------------|----------------|------------------|-----------------|
| `SignalIn` fields | Impossible (validated by Pydantic before reaching debate) | N/A | N/A |
| `RiskProfile` fields | Risk assessment already REJECTED signal before debate | N/A | Already REJECTED |
| `execution_mode` env var | Returns `UNKNOWN` | Rendered as `mode=UNKNOWN`, flag added | Proceed — warning log |
| `guardian_state` lock file | Returns `UNKNOWN` | Rendered as `guardian=UNKNOWN`, flag added | Proceed — warning log |
| `recent_debates` DB query | Returns empty list | Rendered as `none on record` or `DB unavailable` | Proceed — flag added |
| `sovereign_intel` service | Returns default/empty context | T2 section omitted entirely | Proceed — flag added |
| ML prediction | Returns default 50 / NEUTRAL | Rendered as `N/A` | Proceed — flag added |
| RGI trust | Returns NEUTRAL_TRUST | Rendered as `N/A` | Proceed — flag added |

### 7.2 REJECT vs Proceed Decision Tree

```
Is any T1 field missing or malformed?
  YES → REJECT immediately. No LLM call.
  NO  → Continue.

Is the token budget exceeded by T1 fields alone?
  YES → REJECT. Packet is structurally oversized (should never happen with bounded fields).
  NO  → Continue.

Are any T2 fields missing?
  YES → Add missing_data_flags. Omit missing T2 fields. Proceed to LLM.
  NO  → Include all T2 fields. Proceed to LLM.

Token budget exceeded by T1 + T2?
  YES → Drop T2 fields in reverse priority until budget fits. Log each drop.
  NO  → Include T3 fields if surplus. Proceed to LLM.
```

---

## 8. Versioning Policy

### 8.1 Packet Version

The `packet_version` field (currently `DPv1`) is a schema version tag. It changes when:

| Change Type | Version Bump | Example |
|-------------|-------------|---------|
| New T1 field added | Major (`DPv1` → `DPv2`) | Adding `stop_loss` as T1 |
| T1 field removed | Major | Removing `equity_zar` |
| T1 field renamed | Major | `risk_pct` → `risk_fraction` |
| T2 field added | Minor (`DPv1` → `DPv1.1`) | Adding `volatility_regime` |
| T3 field added/removed | Patch (no version bump) | Adding `spread_pct` |
| Encoding format change | Major | Switching from `key=value` to JSON |

### 8.2 Backward Compatibility

- Regression tests are versioned: golden vectors for `DPv1` remain valid until `DPv2`
- Model fine-tuning (if ever applied) is version-locked: a model trained on `DPv1` packets must not receive `DPv2` packets without retraining/validation
- The `packet_version` field is always the first rendered element, so the model (and parser) can identify the schema immediately

---

## 9. Validation Rules

These rules are enforced by the DecisionPacketBuilder (C4) at assembly time:

| # | Rule | Error Code | Action |
|---|------|-----------|--------|
| 1 | All T1 fields present and non-empty | `DPB-001` | REJECT |
| 2 | `symbol` matches `^[A-Z0-9]+$` and ≤ 20 chars | `DPB-002` | REJECT |
| 3 | `side` is exactly `BUY` or `SELL` | `DPB-003` | REJECT |
| 4 | `price` is valid Decimal string, > 0 | `DPB-004` | REJECT |
| 5 | `signal_quantity` is valid Decimal string, > 0 | `DPB-005` | REJECT |
| 6 | `position_size` is valid Decimal string, > 0 | `DPB-006` | REJECT |
| 7 | `risk_pct` is valid Decimal string, 0 < x ≤ 1 | `DPB-007` | REJECT |
| 8 | `execution_mode` is one of allowed values | `DPB-008` | WARN + proceed with `UNKNOWN` |
| 9 | `guardian_state` is one of allowed values | `DPB-009` | WARN + proceed with `UNKNOWN` |
| 10 | `recent_debates` has ≤ 3 entries | `DPB-010` | Truncate to 3 + WARN |
| 11 | No T4 field present in packet | `DPB-011` | FATAL — build error |
| 12 | Total token count ≤ 1,200 | `DPB-012` | REJECT |
| 13 | No `float` type in any numeric field | `DPB-013` | REJECT |
| 14 | `packet_version` matches expected version | `DPB-014` | REJECT |
| 15 | All rendered field values ≤ their max size | `DPB-015` | Truncate + `[…]` for T2/T3, REJECT for T1 |
| 16 | No internal packet contradictions (see §9.1) | `DPB-016` | REJECT |

### 9.1 DPB-016: Internal Packet Contradiction Detection

The DecisionPacketBuilder MUST reject packets that contain conflicting or impossible internal state. A contradictory packet cannot produce a meaningful verdict — the LLM would be reasoning from an impossible premise.

**Contradiction rules (checked at assembly time):**

| # | Contradiction | Fields Involved | Rationale |
|---|--------------|----------------|-----------|
| 1 | `guardian_state=LOCKED` AND `execution_mode=LIVE` AND no `missing_data_flags` acknowledging this | `guardian_state`, `execution_mode`, `missing_data_flags` | If Guardian is LOCKED in LIVE mode, the system should not be submitting signals for debate. This indicates a gate bypass. |
| 2 | `risk_pct` > 1.0 (risk exceeds 100%) | `risk_pct` | Position sizing would exceed total equity — mathematically impossible from a valid risk engine. |
| 3 | `risk_zar` > `equity_zar` | `risk_zar`, `equity_zar` | Risk amount exceeds total equity — impossible from a valid risk engine. |
| 4 | `position_size` ≤ 0 or `price` ≤ 0 | `position_size`, `price` | Zero or negative values passed validation — indicates upstream corruption. |
| 5 | `side` not in {`BUY`, `SELL`} | `side` | Should be caught by DPB-003, but double-checked here for defense in depth. |
| 6 | `history_summary` reports debates but `missing_data_flags` has `history_unavailable=true` | `history_summary`, `missing_data_flags` | Summary claims data exists but flags say it's unavailable — inconsistent assembly. |
| 7 | `rgi_status=AVAILABLE` but `rgi_trust=N/A` | `rgi_status`, `rgi_trust` | RGI reported as available but provided no trust value — indicates silent failure. |
| 8 | `ml_confidence` outside range `[0.0, 100.0]` | `ml_confidence` | ML confidence is bounded; out-of-range values indicate upstream corruption. |
| 9 | `rgi_trust` outside range `[0.0, 100.0]` | `rgi_trust` | Same as above for RGI. |

**On contradiction detection:** Log `DPB-016-CONTRADICTION: {rule_number} — {description}` with full field values for forensic review, then REJECT. No LLM call is made. This is a hard gate — no override, no fallback.

---

## 10. Integration Points

| Component | Reads Packet | Writes Packet | Notes |
|-----------|-------------|---------------|-------|
| `webhook.py` | No | No | Calls DecisionPacketBuilder, passes result to AI Council |
| `DecisionPacketBuilder` (C4) | No | Yes | Assembles packet from data sources |
| `CompactFormatEncoder` (C5) | Yes | Yes | Renders typed packet to compact string |
| `TokenBudgetGuard` (C6) | Yes | No | Validates token count, no mutation |
| `OverflowRejectPolicy` (C7) | Yes | No | Decides REJECT vs drop T2/T3 |
| `ai_council.py` | Yes | No | Receives rendered packet as prompt input |
| `StrictOutputSchema` (C8) | No | No | Validates model OUTPUT (not packet) |
| `PromptVersionRegistry` (C10) | No | No | Provides prompt_version_hash for audit record |
| `ModelFingerprintLogger` (C11) | No | No | Provides model_fingerprint for audit record |
| `GoldenDecisionRegressionSuite` (C13) | Yes | Yes | Builds test packets, validates hashes |

---

## 11. Change Log

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-03-29 | Kiro Agent | Initial Decision Packet Specification (C2 deliverable) |
| 1.1.0 | 2026-03-29 | Kiro Agent | C2 refinements: (1) `recent_debates[]` array replaced with bounded `history_summary` string (T2), (2) explicit per-field bounds table (§4.11), (3) field provenance classification (§4.12), (4) DPB-016 contradiction detection rule (§9.1), (5) Budget Philosophy statement (§1.3). |

---

## 12. Appendix: Token Budget Worksheet

```
Model: qwen3:8b (32,768 token context window)

ALLOCATION:
  System prompt (fixed)          200 tokens
  Decision packet (variable)   1,200 tokens max
    T1 (REQUIRED)                 700 tokens max
    T2 (IMPORTANT)                400 tokens max
    T3 (OPTIONAL)                 100 tokens max
  Output reserve (num_predict)    512 tokens
  Safety margin                   136 tokens
  ─────────────────────────────────────────
  TOTAL ALLOCATED               2,048 tokens
  REMAINING (unused headroom)  30,720 tokens

TYPICAL PACKET (all sections, T1+T2):
  Section A (header)               25 tokens
  Section B (signal)               20 tokens
  Section C (risk)                 25 tokens
  Section D (execution)            12 tokens
  Section E (history, 3 entries)   40 tokens
  Section F (intel, T2 only)       35 tokens
  Section G (missing flags)        10 tokens
  Section H (task instruction)     40 tokens
  Section I (output schema)        30 tokens
  ─────────────────────────────────────────
  TYPICAL TOTAL                   237 tokens (~20% of budget)

WORST CASE (all sections, T1+T2+T3, max field lengths):
  Estimated                       ~450 tokens (~38% of budget)

HEADROOM: Substantial. Budget is conservative by design.
This allows for future T1 field additions without schema version bump concerns.

IMPORTANT: 2,048 tokens is the SAFE OPERATING BUDGET.
It is NOT the maximum theoretical model window (32,768).
The system optimizes for reliability, not maximum context usage.
See §1.3 Budget Philosophy for full rationale.
```
```

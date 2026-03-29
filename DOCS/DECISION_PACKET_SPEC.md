# Decision Packet Specification — DPv1

## Project Autonomous Alpha — Phase 6, Sub-Phase C2

**Version:** DPv1.2
**Status:** ACCEPTED (with refinements R1–R5)
**Reliability Level:** SOVEREIGN TIER
**Target Model:** qwen3:8b (Ollama, 32K context window)
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2026-03-29

---

## 0. Token Budget Philosophy

> **2,048 tokens is the SAFE OPERATING BUDGET — not the maximum theoretical model window.**
>
> qwen3:8b has a 32,768-token context window. This specification intentionally
> constrains total input+output to 2,048 tokens. This is a reliability engineering
> decision, not a technical limitation. The rationale:
>
> 1. **Determinism over capacity.** Smaller prompts produce more consistent verdicts.
> 2. **Headroom for safety.** 30,720 tokens of unused capacity absorbs tokenizer
>    estimation errors, model overhead, and future qwen version variance.
> 3. **Fail-closed budget.** If the packet exceeds 2,048 tokens, the trade is
>    REJECTED — not truncated, not re-packed, not retried with less context.
> 4. **Speed over depth.** On NAS hardware (8GB VRAM), 2K tokens generates in
>    2-5 seconds. 32K would take 30-60 seconds, violating the hot-path latency
>    constraint (FM-02).
>
> The system is intentionally optimizing for reliability, not max context usage.

---

## 1. Purpose

This document defines the **Decision Packet** — the complete, structured input
that the AI Council's LLM receives for every trade signal evaluation.

A Decision Packet is:

- **Complete:** Contains every field the model needs to render a verdict.
- **Bounded:** Every field has a maximum size. Total packet fits within the token budget.
- **Deterministic:** Same inputs → same packet → same hash. No randomness, no optionality in construction.
- **Hashable:** SHA-256 of the serialized packet provides forensic identity.
- **Auditable:** Stored in full alongside the debate result in the audit trail.

A Decision Packet is NOT:

- A conversation. There is no chat history, no multi-turn context.
- A suggestion. Every field is either REQUIRED or explicitly classified.
- Extensible at runtime. The schema is fixed at specification version. New fields require a spec version bump.

---

## 2. Packet Structure

### 2.1 Section Order (Fixed)

The packet is assembled in this exact order. Sections cannot be reordered.

| # | Section | Purpose | Token Budget | Section Code |
|---|---------|---------|-------------|--------------|
| A | System Prompt | Model behavioral contract | 200 | SYS |
| B | Packet Header | Versioning, timestamps | 50 | HDR |
| C | Signal Fields | Raw trade signal from TradingView | 80 | SIG |
| D | Operational Context | Execution mode, guardian state | 60 | OPS |
| E | History Summary | Bounded summary of recent debate history | 100 | HST |
| F | Intelligence Layer | ML confidence, RGI trust, win rate | 150 | INT |
| G | Missing Data Flags | Explicit declaration of unavailable data | 60 | MDF |
| H | Verdict Instruction | Exact output format requirement | 100 | VRD |
| I | Output Reserve | Reserved for model response | 512 | OUT |
| — | Safety Margin | Tokenizer estimation error buffer | 136 | MGN |
| — | **TOTAL** | | **1,448 input + 512 output + 136 margin = 2,096 ≤ 2,048 + margin** | |

> **Budget Allocation:** 1,400 tokens input (sections A–H) + 512 tokens output reserve
> (section I) + 136 tokens safety margin = 2,048 Safe Operating Budget.
> The margin absorbs tokenizer estimation variance. If the pre-margin total
> (sections A–H) exceeds 1,400 tokens, the packet is REJECTED.

---

## 3. Field Reference — Complete Schema

### 3.1 Field Classification Legend

| Classification | Code | Meaning | On Missing |
|---------------|------|---------|------------|
| **REQUIRED** | T1 | Must be present. Omission = REJECT | Trade REJECTED |
| **IMPORTANT** | T2 | Included when available. Omission = flag in Section G | Log + continue |
| **OPTIONAL** | T3 | Included only if token budget allows after T1+T2 | Silent omit |
| **NEVER** | T4 | Explicitly forbidden from the packet | Build error if present |

### 3.2 Field Provenance Legend

| Provenance | Code | Meaning | Examples |
|------------|------|---------|----------|
| **Source-of-Truth** | SoT | Authoritative value from the originating system; no transformation | signal_id, symbol, price, quantity, execution_mode |
| **Derived Summary** | DS | Computed or aggregated from source data by the system | history_summary, win_rate, total_trades |
| **Advisory Metric** | AM | Model output, statistical estimate, or heuristic — informational only, not authoritative | ml_confidence, ml_action, rgi_trust, symbol_bias |

### 3.3 Complete Field Table

| # | Section | Field | Tier | Provenance | Type | Bounds | Description |
|---|---------|-------|------|-----------|------|--------|-------------|
| 1 | B (HDR) | `spec_version` | T1 | SoT | string | Exactly `"DPv1"` (4 chars) | Packet schema version |
| 2 | B (HDR) | `packet_ts` | T1 | SoT | string | ISO-8601 UTC, max 24 chars | Packet assembly timestamp |
| 3 | B (HDR) | `correlation_id` | T1 | SoT | string | UUID v4, exactly 36 chars | Signal correlation identifier |
| 4 | B (HDR) | `prompt_version_hash` | T1 | SoT | string | SHA-256 hex, exactly 64 chars | Hash of the prompt template version |
| 5 | B (HDR) | `model_fingerprint` | T1 | SoT | string | Max 128 chars | Model identifier (name:tag@digest) |
| 6 | C (SIG) | `signal_id` | T1 | SoT | string | Max 64 chars (from SignalIn) | TradingView signal identifier |
| 7 | C (SIG) | `symbol` | T1 | SoT | string | Max 20 chars, `^[A-Z0-9]+$` | Trading pair (e.g., BTCZAR) |
| 8 | C (SIG) | `side` | T1 | SoT | enum | `"BUY"` or `"SELL"` (max 4 chars) | Trade direction |
| 9 | C (SIG) | `price` | T1 | SoT | Decimal | String representation, max 32 chars | Signal price |
| 10 | C (SIG) | `quantity` | T1 | SoT | Decimal | String representation, max 32 chars | Signal quantity |
| 11 | D (OPS) | `execution_mode` | T1 | SoT | enum | `"PAPER"` or `"LIVE"` (max 5 chars) | Current execution mode |
| 12 | D (OPS) | `guardian_locked` | T1 | SoT | boolean | `true` or `false` | Whether guardian has locked trading |
| 13 | D (OPS) | `equity_zar` | T1 | SoT | Decimal | String representation, max 32 chars | Current account equity in ZAR |
| 14 | D (OPS) | `risk_pct` | T1 | SoT | Decimal | String representation, max 8 chars | Risk percentage for this trade |
| 15 | E (HST) | `history_summary` | T1 | DS | string | Max 120 chars (see §3.4) | Bounded summary of recent debate outcomes |
| 16 | F (INT) | `ml_confidence` | T2 | AM | Decimal | String `"0.00"` to `"1.00"`, max 4 chars | ML model confidence score |
| 17 | F (INT) | `ml_action` | T2 | AM | enum | `"BUY"`, `"SELL"`, `"HOLD"` (max 4 chars) | ML model recommended action |
| 18 | F (INT) | `ml_reasoning` | T3 | AM | string | Max 200 chars | ML model reasoning summary |
| 19 | F (INT) | `rgi_trust` | T2 | AM | Decimal | String `"0.00"` to `"1.00"`, max 4 chars | Reward Governor trust probability |
| 20 | F (INT) | `rgi_available` | T1 | SoT | boolean | `true` or `false` | Whether RGI data is available |
| 21 | F (INT) | `win_rate` | T2 | DS | Decimal | String `"0.00"` to `"1.00"`, max 4 chars | Historical win rate for this symbol |
| 22 | F (INT) | `total_trades` | T2 | DS | integer | Max 6 digits (0–999999) | Total historical trades for this symbol |
| 23 | F (INT) | `symbol_bias` | T3 | AM | enum | `"BULLISH"`, `"BEARISH"`, `"NEUTRAL"` (max 7 chars) | Symbol directional bias from analysis |
| 24 | F (INT) | `recent_debates` | T2 | DS | array | Max 3 entries, each max 80 chars (see §3.5) | Last N debate outcomes for same symbol |
| 25 | G (MDF) | `missing_data_flags` | T1 | SoT | array | Max 10 entries, each max 40 chars (see §3.6) | Explicit list of unavailable T2/T3 fields |
| 26 | G (MDF) | `data_quality_grade` | T1 | DS | enum | `"FULL"`, `"PARTIAL"`, `"MINIMAL"` (max 7 chars) | Overall data completeness grade |
| 27 | I (OUT) | `packet_hash` | T1 | SoT | string | SHA-256 hex, exactly 64 chars | Hash of sections A–H (computed last, stored with debate) |
| 28 | A (SYS) | `system_prompt` | T1 | SoT | string | Max 200 tokens (~800 chars) | LLM behavioral contract |

---

### 3.4 History Summary Field (Field #15) — Bounded Format

The `history_summary` field replaces unbounded debate history arrays on the T1 critical path.
It is a REQUIRED field (T1) with DERIVED SUMMARY provenance.

**Format:** Fixed template string with bounded values.

```
"{count} debates ({window}h): {approved} APR, {rejected} REJ, avg_score={avg_score}"
```

**Examples:**

```
"3 debates (24h): 1 APR, 2 REJ, avg_score=35"
"0 debates (24h): 0 APR, 0 REJ, avg_score=0"
"5 debates (24h): 4 APR, 1 REJ, avg_score=72"
```

**Constraints:**

| Parameter | Type | Bound |
|-----------|------|-------|
| `count` | integer | 0–99 |
| `window` | integer | Always `24` (fixed lookback) |
| `approved` | integer | 0–99 |
| `rejected` | integer | 0–99 |
| `avg_score` | integer | 0–100 |
| Total string length | — | Max 120 chars |

**Rationale (refinement R1):** The original specification had `recent_debates[]` as a T1 REQUIRED
array. This was rejected because: (1) hot-path reasoning should not depend on large
debate-history arrays with variable cardinality, (2) the LLM only needs a statistical
summary to contextualize consensus patterns — not full debate text, (3) an unbounded T1
field creates token budget risk that cannot be statically analyzed. The summary field
provides the same decision-relevant information in a fixed-size, deterministic format.

> `recent_debates[]` is retained as a T2 IMPORTANT field (Field #24) for cases when
> extra token budget is available. The history_summary is the T1 minimum.

---

### 3.5 Recent Debates Array (Field #24) — T2 Bounded Format

When included (T2 — token budget permitting), each entry follows this compact format:

```
"{ts_short}|{symbol}|{verdict}|score={score}"
```

**Example entry:** `"03-29T14:30|BTCZAR|REJECTED|score=25"`

**Constraints:**

| Parameter | Bound |
|-----------|-------|
| Max array entries | 3 |
| Max chars per entry | 80 |
| Max total chars (array) | 240 + delimiters |
| `ts_short` format | MM-DDThh:mm (max 11 chars) |
| `verdict` values | `APPROVED` or `REJECTED` only |
| `score` | 0–100 |

**Omission rule:** If the token budget is exhausted after T1 fields, this array is
omitted entirely. Its absence is NOT flagged in `missing_data_flags` (T2 omission
is silent per the tier policy). However, `history_summary` (T1) is ALWAYS present
and provides the minimum required context.

---

### 3.6 Missing Data Flags Array (Field #25) — Bounded Format

Each entry is a structured flag declaring what data was unavailable:

```
"{field_name}:{reason}"
```

**Example entries:**

```
"ml_confidence:SERVICE_UNAVAILABLE"
"rgi_trust:NO_HISTORY"
"win_rate:SYMBOL_NEW"
```

**Constraints:**

| Parameter | Bound |
|-----------|-------|
| Max array entries | 10 |
| Max chars per entry | 40 |
| Max total chars (array) | 400 + delimiters |
| Valid reason codes | `SERVICE_UNAVAILABLE`, `NO_HISTORY`, `SYMBOL_NEW`, `TIMEOUT`, `CALCULATION_ERROR` |

**Rule:** Every T2 field that is missing MUST have a corresponding flag. T3 fields
that are omitted (even due to budget) do NOT require a flag.

---

## 4. Field Provenance Reference (Refinement R3)

Every field's provenance determines how it should be weighted in the LLM's reasoning
and how it should be treated in validation.

### 4.1 Source-of-Truth Fields (SoT)

These fields come directly from an authoritative system and are NOT transformed or
estimated. The LLM should treat these as ground truth.

| Field | Source System | Guarantee |
|-------|--------------|-----------|
| `signal_id` | TradingView webhook | HMAC-verified |
| `symbol` | TradingView webhook | Validated against `^[A-Z0-9]+$` |
| `side` | TradingView webhook | Enum-constrained |
| `price` | TradingView webhook | Decimal (no float) |
| `quantity` | TradingView webhook | Decimal (no float) |
| `execution_mode` | System configuration | Immutable at runtime |
| `guardian_locked` | Guardian subsystem | Real-time state |
| `equity_zar` | Exchange API | Last-fetched balance |
| `risk_pct` | Risk configuration | Decimal (no float) |
| `rgi_available` | Confidence arbiter | Boolean flag |
| `spec_version` | Build constant | `"DPv1"` |
| `packet_ts` | System clock | ISO-8601 UTC |
| `correlation_id` | Signal pipeline | UUID v4 |
| `prompt_version_hash` | Prompt registry | SHA-256 of template |
| `model_fingerprint` | Model registry | name:tag@digest |
| `packet_hash` | Packet builder | SHA-256 of sections A–H |
| `system_prompt` | Prompt file | Version-controlled |
| `missing_data_flags` | Packet builder | Deterministically generated |

### 4.2 Derived Summary Fields (DS)

These fields are computed from source data by the system. The LLM should treat
them as reliable summaries but understand they are aggregations, not raw data.

| Field | Derivation Method | Freshness |
|-------|-------------------|-----------|
| `history_summary` | Aggregated from `ai_debates` table (last 24h, same symbol) | Real-time query |
| `recent_debates` | Last 3 rows from `ai_debates` for same symbol | Real-time query |
| `win_rate` | `wins / total_trades` from execution history | Computed at query time |
| `total_trades` | `COUNT(*)` from execution history for symbol | Computed at query time |
| `data_quality_grade` | Based on count of missing T2 fields: 0=FULL, 1-3=PARTIAL, 4+=MINIMAL | Computed at assembly |

### 4.3 Advisory Metric Fields (AM)

These fields are model outputs, statistical estimates, or heuristics. They are
**informational only** and should NOT be treated as authoritative. The LLM should
weight them as supplementary evidence, not as ground truth.

| Field | Source | Why Advisory |
|-------|--------|--------------|
| `ml_confidence` | ML prediction model | Model estimate; accuracy varies with market regime |
| `ml_action` | ML prediction model | Model recommendation; not a verified signal |
| `ml_reasoning` | ML prediction model | Free-text explanation; subject to model hallucination |
| `rgi_trust` | Reward Governor Index | Historical trust probability; backward-looking metric |
| `symbol_bias` | Market analysis | Heuristic directional assessment; not a prediction |

> **Critical distinction for the LLM:** When `ml_confidence=0.95` and `rgi_trust=0.30`,
> the LLM must NOT treat the high ML confidence as overriding the low RGI trust.
> Both are advisory metrics with independent failure modes. The LLM should note the
> discrepancy and factor it into uncertainty, not cherry-pick the favorable number.

---

## 5. Compact Encoding Rules

### 5.1 Serialization Format

The packet is serialized as compact key-value text (NOT JSON). This minimizes
token usage while maintaining parseability.

```
[HDR]
v=DPv1
ts=2026-03-29T14:30:00Z
cid=a1b2c3d4-e5f6-7890-abcd-ef1234567890
pvh=sha256:abc123...
mfp=qwen3:8b@sha256:def456...

[SIG]
id=TV-BTCZAR-001
sym=BTCZAR
side=BUY
px=1500000.00
qty=0.001

[OPS]
mode=LIVE
guardian=false
equity=50000.00
risk=1.50

[HST]
summary=3 debates (24h): 1 APR, 2 REJ, avg_score=35

[INT]
ml_conf=0.85
ml_act=BUY
rgi_trust=0.92
rgi_avail=true
wr=0.65
trades=42
bias=BULLISH
debates=03-29T14:30|BTCZAR|REJECTED|score=25;03-29T12:15|BTCZAR|APPROVED|score=75;03-28T22:00|BTCZAR|REJECTED|score=30

[MDF]
flags=ml_reasoning:SERVICE_UNAVAILABLE
grade=PARTIAL

[VRD]
Respond with EXACTLY this JSON and nothing else:
{"verdict":"APPROVED"} or {"verdict":"REJECTED"}
Do not explain. Do not add text before or after the JSON.
```

### 5.2 Encoding Rules

| Rule | Spec |
|------|------|
| Section delimiters | `[XXX]` where XXX is the 3-char section code |
| Field separator | `\n` (one field per line) |
| Key-value separator | `=` (first `=` only; values may contain `=`) |
| Array separator (inline) | `;` between entries |
| Array sub-field separator | `|` between fields within an entry |
| String quoting | None. Values are unquoted. |
| Empty value | Omit the field entirely (do not send `key=`) |
| Decimal format | Plain decimal string, no scientific notation, no trailing zeros beyond 2 decimal places |
| Boolean format | `true` or `false` (lowercase) |
| Timestamp format | ISO-8601 UTC (e.g., `2026-03-29T14:30:00Z`) |
| Short timestamp | `MM-DDThh:mm` for array entries |

### 5.3 Token Budget Worksheet

| Section | Max Tokens | Calculation Basis |
|---------|-----------|-------------------|
| A — System Prompt | 200 | Fixed template, version-controlled |
| B — Header | 50 | 5 fields × ~10 tokens each |
| C — Signal | 80 | 5 fields, Decimal strings |
| D — Operations | 60 | 4 fields, short values |
| E — History Summary | 100 | 1 bounded summary string (max 120 chars ≈ 40 tokens) + section overhead |
| F — Intelligence | 150 | Up to 8 fields + 3 debate entries |
| G — Missing Data | 60 | Up to 10 flags + grade |
| H — Verdict Instruction | 100 | Fixed template |
| **Subtotal (A–H)** | **800** | **Nominal (well under 1,400 limit)** |
| I — Output Reserve | 512 | Model response budget |
| Safety Margin | 136 | Tokenizer estimation variance |
| **TOTAL** | **1,448** | **Within 2,048 Safe Operating Budget** |

> **REJECT threshold:** If sections A–H exceed 1,400 tokens, the packet is REJECTED.
> This leaves 512 tokens for model output and 136 tokens for estimation error.

---

## 6. Packet Hash (Field #27)

### 6.1 Construction

```
packet_hash = SHA-256(serialize(sections A through H))
```

### 6.2 Rules

1. The hash is computed AFTER all sections are assembled and encoded.
2. The hash covers the EXACT byte sequence that will be sent to the LLM (minus the system prompt, which is covered by `prompt_version_hash`).
3. The hash is stored in the `ai_debates` table alongside `correlation_id`, `prompt_version_hash`, and `model_fingerprint`.
4. The hash is NOT included in the prompt sent to the LLM (it would change the content being hashed).
5. The hash MUST be generated deterministically — identical inputs MUST always produce identical hashes.
6. The hash MUST be logged with EVERY decision outcome (approved, rejected, or error).
7. The hash MUST be included in audit trail linkage for all downstream records (execution, HITL, risk events).
8. The hash MUST be usable as a regression test key — storing `(packet_hash → expected_verdict)` pairs enables automated golden tests.

### 6.3 Deterministic Generation

The packet hash MUST be deterministically reproducible. Given identical inputs
(signal fields, context source data, system state), the builder MUST produce
bit-identical serialized output, yielding the same SHA-256 hash.

| # | Requirement | How Enforced |
|---|-------------|--------------|
| 1 | Field ordering is fixed (§2.1 section order, §3.3 field numbering) | Builder emits fields in spec-defined order; no hash-map iteration |
| 2 | Decimal formatting is canonical (no trailing zeros beyond 2 decimal places) | Encoding rules §5.2 |
| 3 | Timestamps use UTC with fixed precision (ISO-8601, no timezone offset) | `packet_ts` always `datetime.now(UTC).isoformat() + 'Z'` |
| 4 | Array entries in `recent_debates` ordered chronologically (most recent first) | Builder sorts by timestamp descending before serialization |
| 5 | `missing_data_flags` entries ordered alphabetically by field name | Builder sorts flags before serialization |
| 6 | No whitespace variation — single `\n` between fields, no trailing whitespace | Encoding rules §5.2 |
| 7 | UTF-8 encoding with no BOM | Builder enforces encoding |
| 8 | No randomness in serialization | Fields serialized in fixed section order, fixed field order within sections |

> **Verification:** Two independent calls to `build_packet()` with identical inputs
> MUST produce identical `packet_hash` values. This is enforced by test scenario #13
> and must be verified in the C4 implementation's unit test suite.

### 6.4 Audit Trail Linkage

Every verdict can be fully reconstructed from three immutable identifiers:

```
(packet_hash × prompt_version_hash × model_fingerprint) → verdict
```

The packet hash links across all audit boundaries:

| Audit Record | Hash Field | Purpose |
|-------------|------------|---------|
| `ai_debates` table | `packet_hash` | Links verdict to exact input |
| `signals` table | `packet_hash` (via correlation_id join) | Links signal to decision context |
| HITL approval records | `packet_hash` | Links human review to machine input |
| Risk event logs | `packet_hash` | Links risk incidents to the decision that caused them |
| Regression test vectors | `packet_hash` | Golden test key for determinism verification |

**Mandatory log points:**

| # | Event | What Is Logged | Storage |
|---|-------|----------------|---------|
| 1 | Packet assembly complete | `packet_hash`, `correlation_id`, `spec_version`, `data_quality_grade`, `packet_ts` | Structured log (INFO level) |
| 2 | Pre-LLM validation pass | `packet_hash`, all 18 DPB rule results (pass/fail) | Structured log (INFO level) |
| 3 | Pre-LLM validation fail | `packet_hash`, failing rule ID, failure detail, full serialized packet | Structured log (ERROR level) + `ai_debates` table with `final_verdict=false` |
| 4 | LLM call initiated | `packet_hash`, `model_fingerprint`, `prompt_version_hash` | Structured log (INFO level) |
| 5 | Verdict received | `packet_hash`, raw LLM response, parsed verdict, parse success/failure | `ai_debates` table + structured log |
| 6 | Debate record persisted | `packet_hash` stored in `ai_debates.packet_hash` column alongside `correlation_id`, `bull_reasoning`, `bear_reasoning`, `consensus_score`, `final_verdict` | `ai_debates` table |

**Database schema requirement:** The `ai_debates` table MUST include a
`packet_hash CHAR(64) NOT NULL` column. This column is indexed for
regression query performance.

### 6.5 Regression Testing With Packet Hash

The packet hash enables deterministic regression testing:

1. **Golden vector storage:** Each test vector stores `(inputs, expected_packet_hash, expected_serialized_output)`. The test asserts that `sha256(serialize(build_packet(inputs))) == expected_packet_hash`.

2. **Verdict reproducibility:** For a known `(packet_hash, prompt_version_hash, model_fingerprint)` tuple, the system can replay the exact prompt and compare the verdict against the historical record.

3. **Drift detection:** If a code change causes the same inputs to produce a different `packet_hash`, the golden regression suite catches it immediately. Any hash change requires either (a) a spec version bump or (b) a legitimate bugfix with test vector update.

4. **Cross-environment verification:** The same inputs on different hardware (NAS vs local dev) MUST produce the same `packet_hash`. This validates that serialization is platform-independent.

---

## 7. Validation Rules

### 7.1 Validation Rule Table

Every packet MUST pass ALL validation rules before being sent to the LLM.
Failure of ANY rule = trade REJECTED. No exceptions.

| Rule ID | Name | Severity | Check |
|---------|------|----------|-------|
| DPB-001 | SPEC_VERSION_MATCH | FATAL | `spec_version == "DPv1"` |
| DPB-002 | CORRELATION_ID_PRESENT | FATAL | `correlation_id` is non-empty UUID v4 |
| DPB-003 | SIGNAL_FIELDS_COMPLETE | FATAL | All T1 signal fields (signal_id, symbol, side, price, quantity) present and non-empty |
| DPB-004 | SYMBOL_FORMAT_VALID | FATAL | `symbol` matches `^[A-Z0-9]{2,20}$` |
| DPB-005 | SIDE_ENUM_VALID | FATAL | `side` is exactly `"BUY"` or `"SELL"` |
| DPB-006 | PRICE_POSITIVE_DECIMAL | FATAL | `price` parses as Decimal, `price > 0` |
| DPB-007 | QUANTITY_POSITIVE_DECIMAL | FATAL | `quantity` parses as Decimal, `quantity > 0` |
| DPB-008 | TOKEN_BUDGET_WITHIN_LIMIT | FATAL | Sections A–H total ≤ 1,400 tokens |
| DPB-009 | NO_SILENT_TRUNCATION | FATAL | No field was truncated during assembly |
| DPB-010 | MISSING_FLAGS_CONSISTENT | FATAL | Every missing T2 field has a corresponding `missing_data_flags` entry |
| DPB-011 | EXECUTION_MODE_VALID | FATAL | `execution_mode` is `"PAPER"` or `"LIVE"` |
| DPB-012 | PROMPT_VERSION_HASH_PRESENT | FATAL | `prompt_version_hash` is non-empty SHA-256 hex |
| DPB-013 | MODEL_FINGERPRINT_PRESENT | FATAL | `model_fingerprint` is non-empty, max 128 chars |
| DPB-014 | PACKET_HASH_VALID | FATAL | `packet_hash` == SHA-256(serialized sections A–H) |
| DPB-015 | DATA_QUALITY_GRADE_CONSISTENT | FATAL | Grade matches actual missing-flag count (0=FULL, 1-3=PARTIAL, 4+=MINIMAL) |
| DPB-016 | INTERNAL_PACKET_CONTRADICTION | FATAL | See §7.2 — no conflicting or impossible internal state |
| DPB-017 | CROSS_LAYER_INCONSISTENCY | FATAL | See §7.3 — no logical inconsistency across packet layers |
| DPB-018 | INSUFFICIENT_DECISION_CONTEXT | FATAL | See §7.4 — reject when critical advisory signals are absent or system is degraded |

### 7.2 DPB-016: Internal Packet Contradiction Detection

This rule detects packets with conflicting or impossible internal state.
A contradicted packet reveals data corruption, stale cache, or assembly bugs
that would produce an unreliable verdict.

**Contradiction checks (all must pass):**

| # | Check | Contradiction Example | Rationale |
|---|-------|-----------------------|-----------|
| 1 | `side` vs `ml_action` consistency is NOT required | `side=BUY, ml_action=SELL` is valid | ML may disagree — this is advisory, not contradictory |
| 2 | `guardian_locked=true` AND packet not rejected pre-LLM | Assembly sends packet with guardian locked | If guardian is locked, the trade should be rejected BEFORE packet assembly. A locked packet reaching the LLM indicates a control-flow bypass. |
| 3 | `rgi_available=false` AND `rgi_trust` is present | rgi_trust=0.85 with rgi_available=false | If RGI is unavailable, no trust value should exist. Presence indicates stale/cached data. |
| 4 | `rgi_available=true` AND `rgi_trust` is missing (without flag) | rgi_available=true, no rgi_trust, no missing flag | If RGI is available, trust must be present or explicitly flagged as missing. |
| 5 | `total_trades=0` AND `win_rate > 0` | win_rate=0.50 with total_trades=0 | Cannot have a non-zero win rate with zero trades. |
| 6 | `execution_mode=LIVE` AND `equity_zar=0` | equity_zar=0.00 in LIVE mode | Zero equity in LIVE mode indicates account error or data fetch failure. |
| 7 | `data_quality_grade=FULL` AND `missing_data_flags` is non-empty | grade=FULL but flags=["ml_confidence:TIMEOUT"] | FULL grade means zero missing fields; non-empty flags contradicts this. |
| 8 | `data_quality_grade=MINIMAL` AND `missing_data_flags` has < 4 entries | grade=MINIMAL but only 2 flags | MINIMAL requires 4+ missing fields. |
| 9 | `history_summary` counts inconsistent | summary says "3 debates" but approved + rejected ≠ 3 | Arithmetic inconsistency in derived summary. |
| 10 | `price` or `quantity` is negative or zero | price=0.00 or quantity=-1 | Already caught by DPB-006/007 but double-checked here for defense-in-depth. |

**On contradiction detection:** The packet is REJECTED with error code `DPB-016`.
The specific conflicting fields and check number are logged for debugging.
The contradiction is recorded in the audit trail with full packet context.

---

### 7.3 DPB-017: Cross-Layer Inconsistency Detection

This rule validates alignment ACROSS packet layers — not within a single field
(that is DPB-016's job), but between sections that should tell a coherent story.
A cross-layer inconsistency means the packet assembler combined data from
multiple domains that, taken together, describe an impossible or contradictory
situation.

**Cross-layer checks (all must pass):**

| # | Layer Pair | Check | Contradiction Example | Rationale |
|---|-----------|-------|----------------------|----------|
| 1 | Verdict Instruction (H) vs Signal (C) | Verdict instruction references the correct symbol and side | Instruction says "evaluate ETHZAR BUY" but signal has `sym=BTCZAR side=SELL` | Template injection error or stale instruction cache. |
| 2 | History Summary (E) vs Signal (C) | `history_summary` references the same symbol as the signal | Summary shows ETHZAR debate history but signal is for BTCZAR | Wrong symbol's history was queried. |
| 3 | Intelligence (F) vs Missing Data (G) | If an advisory field is populated, it must NOT also appear in `missing_data_flags` | `ml_confidence=0.85` present AND `ml_confidence:SERVICE_UNAVAILABLE` in flags | Field was both resolved and flagged as missing — data pipeline inconsistency. |
| 4 | Missing Data (G) vs Intelligence (F) | If a T2 advisory field is absent from the packet, it MUST appear in `missing_data_flags` | `rgi_trust` omitted but no corresponding flag | Silent omission of T2 field violates DPB-010, but this is a cross-layer verification. |
| 5 | Intelligence (F) vs Operations (D) | `rgi_trust` value alignment with `execution_mode` | `execution_mode=PAPER` but `rgi_trust` derived from LIVE execution history | Trust metric from wrong execution context contaminates the verdict. |
| 6 | History Summary (E) vs Intelligence (F) | `history_summary` claim of "0 debates" vs `recent_debates` containing entries | Summary says no debates but recent_debates array is non-empty | Derived summary contradicts the detailed records it was derived from. |
| 7 | Operations (D) vs Intelligence (F) | Risk assessment coherence | `risk_pct=10.00` (high risk) but `ml_confidence=0.99` AND `win_rate=0.20` (20% win rate) is not contradictory — ML may disagree with history. This check is NOT applied. | Advisory metrics may legitimately disagree with each other. Only structural contradictions are flagged, not analytical disagreements. |

> **Design principle:** DPB-017 checks structural coherence between layers, not
> analytical agreement between advisory metrics. Two advisory metrics that disagree
> (e.g., `ml_confidence=0.95` vs `rgi_trust=0.30`) is VALID — that is exactly the
> kind of uncertainty the LLM should evaluate. But a populated field that is
> simultaneously flagged as missing is a structural defect.

**On detection:** REJECT with error code `DPB-017`. Log the specific check number,
the conflicting layers, and the field values involved.

---

### 7.4 DPB-018: Insufficient Decision Context

This rule enforces a MINIMUM VIABLE CONTEXT threshold. Even though T2 field
absence is individually tolerable (flag + continue), there exists a point where
so much context is missing that the LLM's verdict has no evidentiary foundation.

DPB-018 defines that threshold and REJECTS packets below it.

**Insufficiency checks (any failure = REJECT):**

| # | Check | Threshold | Rationale |
|---|-------|-----------|-----------|
| 1 | Excessive missing data flags | `len(missing_data_flags) >= 5` | With 5+ of 6 T2 fields missing, the LLM has only T1 signal fields and operational context. The verdict is structurally uninformed. |
| 2 | All critical advisory signals missing | `ml_confidence` AND `rgi_trust` AND `win_rate` all absent | These three fields represent the three independent evidence dimensions (ML model, Reward Governor, historical track record). If ALL three are unavailable, the LLM has zero quantitative context beyond the raw signal. |
| 3 | Insufficient historical context | `history_summary` reports `"0 debates (24h)"` AND `total_trades=0` (or missing) AND `win_rate` missing | Symbol has never been traded and has no debate history. The LLM has no basis for pattern recognition. |
| 4 | System state degraded beyond safe threshold | `data_quality_grade="MINIMAL"` AND `execution_mode="LIVE"` | In LIVE mode with MINIMAL data quality, the risk of an uninformed APPROVED verdict on real capital is unacceptable. PAPER mode with MINIMAL is allowed (no capital at risk). |
| 5 | Intelligence layer completely unreachable | ALL of: `ml_confidence` missing, `ml_action` missing, `rgi_trust` missing, `win_rate` missing, `total_trades` missing, `recent_debates` missing | Every T2 field failed resolution. The packet is a naked signal with no intelligence enrichment. Even in PAPER mode, this indicates a systemic failure that should be investigated, not auto-approved. |

**Interaction with data_quality_grade:**

| Grade | DPB-018 Behavior |
|-------|------------------|
| `FULL` | DPB-018 never triggers (by definition, no missing fields). |
| `PARTIAL` | DPB-018 may trigger if the specific missing fields hit check #2 or #3. |
| `MINIMAL` | DPB-018 always evaluates checks #1, #4, #5. High probability of rejection. |

**On detection:** REJECT with error code `DPB-018`. Log the specific check number,
the missing fields, and the data_quality_grade. Record in audit trail as
`rejection_reason="INSUFFICIENT_DECISION_CONTEXT"` — distinct from T1 missing
(which is `"T1_FIELD_MISSING"`) and contradiction (which is `"INTERNAL_CONTRADICTION"`).

> **Why this is not redundant with data_quality_grade:** The grade tells the LLM
> about data completeness so it can adjust confidence. DPB-018 tells the SYSTEM
> that data completeness is below the minimum threshold for ANY verdict to be
> meaningful. The grade is information for the model; DPB-018 is a circuit breaker
> for the system.

---

## 8. Omission and Degradation Policy

### 8.1 Tier 1 (REQUIRED) — Omission = REJECT

If ANY T1 field cannot be populated, the entire packet is invalid.
The system MUST NOT attempt to construct a "partial" packet.
The trade is REJECTED immediately.

**T1 Fields (18 total):**
spec_version, packet_ts, correlation_id, prompt_version_hash, model_fingerprint,
signal_id, symbol, side, price, quantity, execution_mode, guardian_locked,
equity_zar, risk_pct, history_summary, rgi_available, missing_data_flags,
data_quality_grade.

> Note: `system_prompt` and `packet_hash` are also T1 but are assembled by the
> builder, not sourced from external systems. Their absence indicates a build bug,
> not a data availability issue.

### 8.2 Tier 2 (IMPORTANT) — Omission = Flag + Continue

If a T2 field cannot be populated:

1. The field is omitted from the packet.
2. A corresponding entry is added to `missing_data_flags`.
3. `data_quality_grade` is recalculated.
4. Assembly continues.

**T2 Fields (6 total):**
ml_confidence, ml_action, rgi_trust, win_rate, total_trades, recent_debates.

### 8.3 Tier 3 (OPTIONAL) — Silent Omission

T3 fields are included only if token budget allows after T1+T2.
Omission is silent — no flag is generated.

**T3 Fields (2 total):**
ml_reasoning, symbol_bias.

### 8.4 Tier 4 (NEVER) — Forbidden Content

The following MUST NEVER appear in a decision packet:

- Raw user input or free-form text not from a controlled source
- PII (personal identifiable information)
- API keys, secrets, or credentials
- Full debate reasoning text from prior debates (only summary/compact format allowed)
- Floating-point numbers (all numerics must be Decimal string representations)
- Content from external URLs or web scraping
- Multi-turn conversation history

---

## 9. Per-Field Bounds Summary (Refinement R2)

All variable-size fields with their maximum bounds in one reference table:

| Field | Type | Max Length / Cardinality | Overflow Action |
|-------|------|------------------------|-----------------|
| `signal_id` | string | 64 chars | REJECT (DPB-003) |
| `symbol` | string | 20 chars | REJECT (DPB-004) |
| `price` | Decimal string | 32 chars | REJECT (DPB-006) |
| `quantity` | Decimal string | 32 chars | REJECT (DPB-007) |
| `equity_zar` | Decimal string | 32 chars | REJECT |
| `risk_pct` | Decimal string | 8 chars | REJECT |
| `correlation_id` | string | 36 chars (UUID v4) | REJECT (DPB-002) |
| `prompt_version_hash` | string | 64 chars (SHA-256) | REJECT (DPB-012) |
| `model_fingerprint` | string | 128 chars | REJECT (DPB-013) |
| `packet_hash` | string | 64 chars (SHA-256) | REJECT (DPB-014) |
| `history_summary` | string | 120 chars | REJECT (format violation) |
| `ml_confidence` | Decimal string | 4 chars (`"0.00"`–`"1.00"`) | REJECT (range violation) |
| `ml_action` | enum string | 4 chars | REJECT (enum violation) |
| `ml_reasoning` | string | 200 chars | Truncate to 200; if T3, silently omit instead |
| `rgi_trust` | Decimal string | 4 chars (`"0.00"`–`"1.00"`) | REJECT (range violation) |
| `win_rate` | Decimal string | 4 chars (`"0.00"`–`"1.00"`) | REJECT (range violation) |
| `total_trades` | integer | 6 digits (0–999999) | REJECT (range violation) |
| `symbol_bias` | enum string | 7 chars | REJECT (enum violation) |
| `recent_debates` | array | Max 3 entries × 80 chars each | Drop excess entries (keep most recent 3) |
| `missing_data_flags` | array | Max 10 entries × 40 chars each | Log overflow; keep first 10 |
| `data_quality_grade` | enum string | 7 chars | REJECT (enum violation) |
| `system_prompt` | string | 200 tokens (~800 chars) | REJECT (DPB-008 via token budget) |

> **Overflow policy:** T1 field bounds exceeded = REJECT. T2 bounds exceeded = truncate
> individual field to bound + log warning. T3 bounds exceeded = omit field entirely.
> The ONLY exception to the no-truncation rule is `ml_reasoning` (T3), which may be
> truncated because it is an advisory free-text field with no structural significance.

---

## 10. Token Pressure Simulation Requirement (Refinement R5)

Before the DecisionPacketBuilder (C4) is accepted as complete, a token pressure
simulation MUST be executed and results documented.

### 10.1 Purpose

The token pressure simulation validates that the tier-based field inclusion
algorithm and overflow resolution sequence behave correctly under budget
stress. This is a SPECIFICATION VALIDATION exercise, not a runtime test.

### 10.2 Simulation Scenarios

| # | Scenario | Setup | Expected Behavior |
|---|----------|-------|-------------------|
| TP-01 | Near budget — T3 boundary | Construct packet where T1+T2 = 1,350 tokens (50 remaining). T3 fields total 60 tokens. | T3-P1 (ml_reasoning, ~40 tokens) attempted. If fits, included. T3-P2 (symbol_bias, 3 tokens) attempted next. If combined exceeds budget, T3-P2 silently omitted. No flags generated. |
| TP-02 | At budget — T2 tail drop | Construct packet where T1 = 1,300 tokens (artificially inflated system prompt). Only 100 tokens remain for T2. | T2-P1 through T2-P4 fit (~12 tokens). T2-P5 fits (~3 tokens). T2-P6 (recent_debates, ~60 tokens) does NOT fit → flagged as TOKEN_BUDGET_EXHAUSTED. All T3 omitted silently. |
| TP-03 | Over budget — T2 progressive drop | Construct packet where T1 = 1,380 tokens. Only 20 tokens remain. | T2-P1 (rgi_trust, 3 tokens) fits. T2-P2 (ml_confidence, 3 tokens) fits. T2-P3 (ml_action, 2 tokens) fits. T2-P4 (win_rate, 3 tokens) fits. T2-P5 (total_trades, 3 tokens) fits. T2-P6 does NOT fit → flagged. All T3 omitted. |
| TP-04 | Extreme pressure — T2 full drop | Construct packet where T1 = 1,398 tokens. Only 2 tokens remain. | ALL T2 fields flagged as TOKEN_BUDGET_EXHAUSTED. ALL T3 omitted. `data_quality_grade=MINIMAL`. Packet valid but DPB-018 check #2 triggers (5+ missing flags) → REJECT. |
| TP-05 | T1 exceeds budget (specification error) | Construct packet where T1 alone = 1,450 tokens. | REJECT with code T1_BUDGET_EXCEEDED. This is a build-time error indicating specification drift. Escalate immediately. |
| TP-06 | Overflow resolution sequence | Start with full packet (all tiers) at 1,420 tokens (20 over). | Overflow handler drops T3 first (-23 to -63 tokens). If still over: T2-P6 dropped, then T2-P5, etc. Verify T1 NEVER dropped. |

### 10.3 Validation Criteria

| Criterion | Requirement |
|-----------|-------------|
| Tier 3 dropped first | ALL T3 fields must be dropped before ANY T2 field |
| Tier 2 dropped in correct priority order | T2-P6 first, T2-P5 second, ..., T2-P1 last (reverse priority) |
| Tier 1 never dropped | Under NO scenario may a T1 field be omitted or truncated |
| Rejection threshold | When remaining fields constitute insufficient context (DPB-018), the packet is REJECTED — not sent to the LLM |
| Flags generated correctly | Every dropped T2 field has a corresponding `missing_data_flags` entry with reason `TOKEN_BUDGET_EXHAUSTED` or `TOKEN_BUDGET_OVERFLOW` |
| Grade recalculated | `data_quality_grade` reflects the actual post-drop missing-flag count |
| Deterministic behavior | Identical inputs produce identical drop decisions across runs |

### 10.4 Documentation Requirement

The simulation results MUST be documented in the C4 implementation deliverable
with the following format:

```
## Token Pressure Simulation Results

| Scenario | T1 Tokens | T2 Included | T3 Included | Flags | Grade | Outcome |
|----------|-----------|-------------|-------------|-------|-------|---------|
| TP-01    | ...       | ...         | ...         | ...   | ...   | PASS/FAIL |
| ...      | ...       | ...         | ...         | ...   | ...   | ...     |
```

> **Gate condition:** C4 is not accepted unless ALL 6 token pressure simulation
> scenarios produce the expected behavior documented in §10.2.

---

## 11. LLM Interpretation Contract (Refinement R5)

The Decision Packet is not just a data structure — it is a CONTRACT between
the system and the LLM. This section defines mandatory interpretation rules
that the system prompt (Section A) MUST encode.

### 11.1 Missing Data Flag Interpretation

When `missing_data_flags` is non-empty, the LLM MUST:

| # | Rule | Rationale |
|---|------|-----------|
| 1 | **Do NOT infer or hallucinate values for missing fields.** If `ml_confidence` is flagged as missing, the LLM must NOT estimate what it might have been. The absence is a fact, not a gap to fill. | LLM inference of missing data introduces unauditable fabrication into the decision path. |
| 2 | **Treat each missing flag as NEGATIVE evidence.** A missing advisory metric is not neutral — it reduces the evidence base for APPROVED. The LLM should weight absence as increasing uncertainty. | "Absence of evidence" in a system that SHOULD have evidence is itself evidence of system degradation. |
| 3 | **Explicitly acknowledge missing fields in reasoning.** The model's output reasoning must reference the missing data if the verdict is APPROVED. An APPROVED verdict that ignores missing data is structurally suspect. | Ensures the LLM's reasoning is traceable and the operator can verify that missing data was considered. |
| 4 | **Never substitute default values.** The LLM must NOT treat a missing `rgi_trust` as `rgi_trust=0.50` (neutral) or `rgi_trust=1.00` (optimistic). Missing means UNKNOWN, not DEFAULT. | Default substitution masks the actual system state and can lead to false confidence. |

**System prompt encoding:**

```
When [MDF] flags are present:
- Do NOT infer, estimate, or assume values for flagged fields.
- Treat each missing field as reducing your confidence.
- If you APPROVE despite missing data, you MUST state why the
  available evidence is sufficient without the missing fields.
- Never substitute default values for missing fields.
```

### 11.2 Advisory Metric Subordination

Advisory metrics (AM provenance) MUST NOT override Source-of-Truth (SoT) fields.

| # | Rule | Example |
|---|------|---------|
| 1 | **Advisory metrics inform, SoT fields decide.** The signal (`symbol`, `side`, `price`, `quantity`) and operational state (`execution_mode`, `guardian_locked`, `equity_zar`) are ground truth. Advisory metrics like `ml_confidence` and `rgi_trust` are supplementary. | `ml_confidence=0.99` does NOT override the fact that `equity_zar=500.00` (dangerously low equity for a LIVE trade). |
| 2 | **Conflicting advisory metrics INCREASE uncertainty.** When `ml_confidence` and `rgi_trust` disagree significantly, the LLM must NOT cherry-pick the favorable one. Divergence is a signal of uncertainty. | `ml_confidence=0.95, rgi_trust=0.25` — the LLM should flag this divergence, not average them to 0.60 and call it moderate. |
| 3 | **Advisory metrics cannot justify overriding operational constraints.** If `equity_zar` is low, `risk_pct` is high, or `history_summary` shows a pattern of rejections, no advisory metric can override these operational realities. | `win_rate=0.80` does not justify APPROVED if the last 5 debates were all REJECTED and the current `risk_pct=8.00`. |

**System prompt encoding:**

```
Field hierarchy:
1. Source-of-truth fields ([SIG], [OPS]) are GROUND TRUTH. Never override.
2. Derived summaries ([HST]) are RELIABLE AGGREGATIONS. Weight highly.
3. Advisory metrics ([INT]) are INFORMATIONAL ONLY. Use as supplementary
   evidence. When advisory metrics conflict with each other, increase
   uncertainty — do not average or cherry-pick.
```

### 11.3 Low-Quality Context Response

When `data_quality_grade` is degraded, the LLM MUST adjust its confidence
threshold accordingly.

| Grade | LLM Behavior Contract |
|-------|-----------------------|
| `FULL` | Normal evaluation. All evidence available. APPROVE if signal and context warrant it. |
| `PARTIAL` | Elevated caution. Missing advisory signals reduce the evidence base. Require STRONGER signal-level indicators for APPROVED. If the signal is marginal, default to REJECTED. |
| `MINIMAL` | Maximum caution. The LLM has almost no advisory context. APPROVED requires overwhelming signal-level evidence (extremely favorable price, strong history summary, low risk percentage). When in doubt, REJECT. |

**System prompt encoding:**

```
Data quality response:
- grade=FULL: Evaluate normally with all available evidence.
- grade=PARTIAL: Raise your approval threshold. Missing data means
  less certainty. Marginal signals should be REJECTED.
- grade=MINIMAL: Near-maximum caution. Only approve if the signal
  is unambiguously strong on its own merits. Default to REJECTED.
```

### 11.4 Contradiction Signal Response

If contradiction signals survive to the LLM (they should be caught by DPB-016
and DPB-017, but defense-in-depth requires the LLM to act as a final barrier):

| # | Rule |
|---|------|
| 1 | If any field values appear internally inconsistent (e.g., `win_rate=0.80` but `history_summary` shows mostly REJECTEDs), the LLM MUST default to REJECTED. |
| 2 | If advisory metrics strongly contradict each other (e.g., `ml_confidence=0.95` vs `rgi_trust=0.15`), the LLM MUST NOT resolve the contradiction by favoring either metric. It MUST REJECT on the basis of unresolvable uncertainty. |
| 3 | If the `missing_data_flags` suggest systemic failure (3+ flags with `SERVICE_UNAVAILABLE` or `TIMEOUT`), the LLM should interpret this as infrastructure degradation and strongly bias toward REJECTED. |

**System prompt encoding:**

```
Contradiction handling:
- If field values appear internally inconsistent: REJECT.
- If advisory metrics strongly contradict each other: REJECT.
  Do NOT average, interpolate, or pick the favorable number.
- If 3+ fields are missing due to SERVICE_UNAVAILABLE or TIMEOUT:
  Treat as infrastructure degradation. Strongly prefer REJECTED.
```

---

## 12. Versioning Policy

### 12.1 Version Format

```
DPv{major}.{minor}
```

- **Major:** Breaking changes (new T1 fields, removed fields, section reorder). Requires prompt update + model re-validation.
- **Minor:** Non-breaking additions (new T2/T3 fields, new validation rules, bound adjustments).

### 12.2 Current Version

```
DPv1 (= DPv1.0, initial release with refinements R1–R8)
```

### 12.3 Compatibility Rules

1. A packet with `spec_version=DPv1` must validate against the DPv1 rule set.
2. The DecisionPacketBuilder refuses to construct packets for unknown spec versions.
3. Spec version is stored in the audit trail alongside the debate result.
4. Prompt templates reference the spec version. A prompt designed for DPv1 must not be used with DPv2.

---

## 13. Change Log

| Version | Date | Author | Change |
|---------|------|--------|--------|
| DPv1 | 2026-03-29 | Kiro Agent | Initial specification. 9 sections, 28 fields, 4 tiers, 15 validation rules, compact encoding format, SHA-256 packet hash. |
| DPv1.1 | 2026-03-29 | Kiro Agent | **Refinement R1:** `recent_debates[]` downgraded from T1→T2; replaced with bounded `history_summary` (T1, max 120 chars). **Refinement R2:** Explicit per-field bounds table added (§9). **Refinement R3:** Field provenance classification added (§4) — SoT/DS/AM for all 28 fields. **Refinement R4:** DPB-016 INTERNAL_PACKET_CONTRADICTION validation rule added (§7.2) with 10 contradiction checks. **Budget clarity:** 2,048 tokens explicitly defined as Safe Operating Budget (§0). |
| DPv1.2 | 2026-03-29 | Kiro Agent | **Refinement R5:** DPB-017 CROSS_LAYER_INCONSISTENCY added (§7.3) — validates alignment across task instruction, strategy, risk summary, and missing data layers with 7 cross-layer checks. DPB-018 INSUFFICIENT_DECISION_CONTEXT added (§7.4) — rejects packets with critical advisory gaps, excessive missing flags, or degraded system state with 5 insufficiency checks and grade interaction matrix. LLM Interpretation Contract added (§10) — explicit behavioral rules for missing_data_flags (no inference), advisory metric weighting (no override), low-quality context (reduce confidence), and contradiction signals (force rejection). Token Pressure Simulation requirement added (§11) — 6 simulation scenarios with validation criteria and documentation gate for C4 acceptance. Packet hash rules expanded (§6.2–6.4) — deterministic generation, audit trail linkage across all downstream records, regression test key usage. Total validation rules: 18 (DPB-001 through DPB-018). |

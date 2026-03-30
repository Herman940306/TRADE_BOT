# Phase 12C/D/F — Qwen Prompt Optimization

## Summary

Phase 12 Sections C, D, and F rebuilt both FAST and DEEP mode system prompts for the qwen3:8b model and tuned generation parameters for tighter, regime-aware operation.

---

## Changes

### FAST Mode Prompt (`app/prompts/fast_prompt_contract.txt`)

| Aspect | Phase 11 | Phase 12 |
| --- | --- | --- |
| Directive | Generic `/no_think` | `/no_think` + regime-aware rules |
| Regime handling | None | Explicit RANGING/VOLATILE rejection (rule 3) |
| Trend alignment | Implicit | Explicit trend confirmation (rules 4-5) |
| Speculation guard | None | Ban on speculative language (rule 6) |
| Spec version | DPv1 | DPv2 |

Key rules added:

1. Output format: `---VERDICT---` / `---END---` block
2. If `regime == RANGING` or `VOLATILE`, respond `REJECT` with no analysis
3. LONG requires BULL trend + EMA alignment
4. No speculative language ("might", "could")

### DEEP Mode Prompt (`app/prompts/deep_prompt_contract.txt`)

| Aspect | Phase 11 | Phase 12 |
| --- | --- | --- |
| Analysis structure | Unbounded free-form | Bounded 4-step (1-2 sentences each) |
| Steps | Generic | 1. Contradictions, 2. Missing data, 3. Fact/Inference, 4. Escalation |
| Regime handling | None | Explicit RANGING/VOLATILE rejection (rule 3) |
| Fact tagging | None | `[FACT]` / `[INFERENCE]` separation |
| Spec version | DPv1 | DPv2 |

### Mode Configuration (`app/logic/reasoning_mode.py`)

| Parameter | FAST (Ph11) | FAST (Ph12) | DEEP (Ph11) | DEEP (Ph12) |
| --- | --- | --- | --- | --- |
| temperature | 0.30 | **0.15** | 0.20 | **0.10** |
| num_predict | 256 | **192** | 512 | **384** |
| timeout_seconds | 30 | **25** | 60 | **45** |
| target_latency | 8s | **6s** | 20s | **15s** |
| thinking_enabled | False | False | True | True |

### Budget Invariants (Unchanged)

| Mode | Input | Output Reserve | Safety Margin | Total |
| --- | --- | --- | --- | --- |
| FAST | 1400 | 512 | 136 | 2048 |
| DEEP | 1800 | 640 | 160 | 2600 |

## Rationale

1. **Lower temperature** reduces hallucination and speculative verdicts on a 8B model.
2. **Reduced `num_predict`** forces concise output — the model cannot ramble past the token limit.
3. **Tighter timeouts** enforce latency discipline. If the model cannot decide in 25s (FAST) or 45s (DEEP), the signal is stale.
4. **Regime-aware prompts** provide the model with explicit rejection rules, reducing cases where the LLM overrides regime safety with speculative confidence.
5. **DPv2 spec** ensures prompt/schema version tracking for future audits.

## Files Changed

| File | Change |
| --- | --- |
| `app/prompts/fast_prompt_contract.txt` | Rebuilt with regime rules, DPv2 |
| `app/prompts/deep_prompt_contract.txt` | Rebuilt with 4-step analysis, DPv2 |
| `app/logic/reasoning_mode.py` | Temperature, num_predict, timeout reduced |
| `tests/unit/test_phase12_regime_strict.py` | 10 prompt contract + 11 mode config tests |

## Safety Assessment

- **Budget invariants preserved:** Total safe operating budget unchanged at 2048 (FAST) and 2600 (DEEP).
- **Thinking mode unchanged:** FAST=disabled, DEEP=enabled — escalation path intact.
- **No floating-point in prompt:** All numeric values in prompts are display-only context; execution uses `Decimal`.

# Qwen Final Hardening Report — Phase 12.5

**Date:** 2025-07-06
**Status:** HARDENED
**Model:** qwen3:8b (local GPU — GTX 1080 Ti)

## Summary

Phase 12.5 updated both FAST and DEEP prompt contracts to reflect the new
REGIME_WEAK_TRENDING rejection gate. No changes were made to model
configuration or temperature/budget parameters (those were already optimized
in Phase 12).

## Prompt Changes

### FAST Prompt (`fast_prompt_contract.txt`)

**Added rule 4:**
> If regime is TRENDING but regime_confidence < 0.60, output REJECTED with
> reason_code FAST-REJECT-RISK. Weak trends have no proven edge.

Rules 5–8 renumbered (were 4–7).

### DEEP Prompt (`deep_prompt_contract.txt`)

**Added rule 4:**
> If regime is TRENDING but regime_confidence < 0.60, output REJECTED.
> Weak/marginal trends are not tradeable.

Rules 5–9 renumbered (were 4–8).

## Configuration (Unchanged from Phase 12)

| Parameter | FAST | DEEP |
|-----------|------|------|
| Temperature | 0.15 | 0.10 |
| num_predict | 192 | 384 |
| Timeout (s) | 25 | 45 |
| Thinking | Disabled | Enabled |
| Safe budget | 2048 | 2600 |
| Target latency | 6s | 15s |

## Test Coverage

- `test_fast_prompt_has_weak_trending_rule` — PASS
- `test_deep_prompt_has_weak_trending_rule` — PASS
- All 10 existing TestPromptContracts tests — PASS
- All 10 TestModeConfiguration tests — PASS

## Verdict

QWEN HARDENING: **COMPLETE**. Prompts now reflect all rejection gates including
the new weak TRENDING gate. Model configuration remains optimal from Phase 12.
No further prompt changes needed for freeze.

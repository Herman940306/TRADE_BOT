# Context Priority Policy — CPPv1

## Project Autonomous Alpha — Phase 6, Sub-Phase C3

**Version:** CPPv1.1
**Status:** ACCEPTED (with governance amendments)
**Parent Spec:** [DECISION_PACKET_SPEC.md](DECISION_PACKET_SPEC.md) (DPv1.2)
**Reliability Level:** SOVEREIGN TIER
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2026-03-29

---

## 0. Purpose

This document defines the **Context Priority Policy** — the deterministic rules
that govern which fields enter the Decision Packet, in what order, and what happens
when data is unavailable or the token budget is exceeded.

The policy answers three questions:

1. **What MUST be in the packet?** (Tier 1 — failure = REJECT)
2. **What SHOULD be in the packet?** (Tier 2 — failure = flag + continue)
3. **What MAY be in the packet?** (Tier 3 — included only if budget allows)

And one prohibition:

1. **What MUST NEVER be in the packet?** (Tier 4 — presence = build error)

This is a POLICY document. It defines the rules. The DecisionPacketBuilder (C4)
is the ENFORCEMENT mechanism that implements these rules in code.

---

## 1. Tier Definitions

### 1.1 Tier 1 — MUST-INCLUDE (REQUIRED)

**Semantics:** The packet cannot exist without these fields. If ANY T1 field
cannot be resolved, the packet is invalid. The trade is REJECTED before
the LLM is called. No partial T1 packets are ever constructed.

**Token allocation:** T1 fields get FIRST claim on the input budget. Their
combined token cost is the minimum viable packet size. If T1 alone exceeds
the 1,400-token input limit, this indicates a specification error (not a
runtime condition) and must be escalated as a build-time failure.

**On resolution failure:**

```
T1 field missing → REJECT immediately
                 → Log: "DPB-003: T1 field {field_name} unresolvable, source={source}, reason={reason}"
                 → Record rejection in ai_debates with packet_hash=NULL (packet never assembled)
                 → DO NOT call the LLM
```

**T1 Field Inventory (18 fields):**

| # | Field | Source | Resolution | Estimated Tokens |
|---|-------|--------|------------|-----------------|
| 1 | `spec_version` | Build constant | Hardcoded `"DPv1"` | 2 |
| 2 | `packet_ts` | System clock | `datetime.now(UTC).isoformat()` | 8 |
| 3 | `correlation_id` | Signal pipeline | Passed from webhook handler | 12 |
| 4 | `prompt_version_hash` | Prompt registry (C10) | SHA-256 of active prompt template | 18 |
| 5 | `model_fingerprint` | Model registry (C11) | Active model identifier | 12 |
| 6 | `signal_id` | SignalIn schema | Webhook payload field | 8 |
| 7 | `symbol` | SignalIn schema | Webhook payload field | 3 |
| 8 | `side` | SignalIn schema | Webhook payload field | 2 |
| 9 | `price` | SignalIn schema | Webhook payload field, Decimal→str | 6 |
| 10 | `quantity` | SignalIn schema | Webhook payload field, Decimal→str | 4 |
| 11 | `execution_mode` | System configuration | `settings.EXECUTION_MODE` | 3 |
| 12 | `guardian_locked` | Guardian subsystem | Query guardian state | 2 |
| 13 | `equity_zar` | Exchange API (cached) | Last-fetched balance | 6 |
| 14 | `risk_pct` | Risk configuration | `settings.RISK_PERCENTAGE` | 3 |
| 15 | `history_summary` | `ai_debates` table | Aggregate query (last 24h, same symbol) | 15 |
| 16 | `rgi_available` | Confidence arbiter | Boolean availability check | 2 |
| 17 | `missing_data_flags` | Packet builder | Computed during T2 resolution | 8 |
| 18 | `data_quality_grade` | Packet builder | Computed from missing-flag count | 2 |
| — | `system_prompt` | Prompt file | Version-controlled template | 200 |
| — | `packet_hash` | Packet builder | SHA-256 computed after assembly | 18 |
| — | **T1 TOTAL** | | | **~334** |

> T1 nominal cost: ~334 tokens. This is well within the 1,400-token input budget,
> leaving ~1,066 tokens for T2 fields, T3 fields, and section delimiters.

---

### 1.2 Tier 2 — SHOULD-INCLUDE (IMPORTANT)

**Semantics:** These fields materially improve verdict quality. They are included
when available. If a T2 field cannot be resolved (service down, no history, timeout),
the field is omitted and a `missing_data_flags` entry is created.

**Token allocation:** T2 fields get SECOND claim on the remaining budget after T1.
T2 fields are resolved in PRIORITY ORDER (see §2.2). If the budget is exhausted
during T2 resolution, remaining T2 fields are treated as unavailable.

**On resolution failure:**

```
T2 field missing → Add "{field_name}:{reason}" to missing_data_flags
                 → Recalculate data_quality_grade
                 → Continue packet assembly
                 → DO NOT REJECT
```

**On budget exhaustion during T2:**

```
T2 field resolved but budget insufficient
  → Treat as missing with reason "TOKEN_BUDGET_EXHAUSTED"
  → Add to missing_data_flags
  → Continue with remaining budget (if any) for lower-priority T2 fields
  → This is NOT a rejection. The packet degrades gracefully.
```

**T2 Field Inventory (6 fields, in priority order):**

| Priority | Field | Source | Resolution | Estimated Tokens | Rationale |
|----------|-------|--------|------------|-----------------|-----------|
| T2-P1 | `rgi_trust` | Confidence arbiter | `get_trust_probability(symbol)` | 3 | Most directly impacts verdict calibration |
| T2-P2 | `ml_confidence` | ML prediction model | `predict(signal)` | 3 | Quantitative confidence signal |
| T2-P3 | `ml_action` | ML prediction model | Same call as ml_confidence | 2 | Directional recommendation |
| T2-P4 | `win_rate` | Execution history DB | `SELECT wins/total WHERE symbol=?` | 3 | Symbol-specific track record |
| T2-P5 | `total_trades` | Execution history DB | Same query as win_rate | 3 | Sample size context for win_rate |
| T2-P6 | `recent_debates` | `ai_debates` table | Last 3 rows for symbol, compact format | 30–90 | Detailed debate context (summary already in T1) |
| — | **T2 TOTAL (all resolved)** | | | **~44–104** |

> T2 nominal cost: 44 tokens (without recent_debates) to 104 tokens (with 3 debate entries).

---

### 1.3 Tier 3 — MAY-INCLUDE (OPTIONAL)

**Semantics:** These fields provide supplementary context but do not materially
affect verdict quality. They are included ONLY if all T1 and T2 fields are
resolved AND token budget remains.

**Token allocation:** T3 fields get LAST claim on whatever budget remains after
T1 + T2. If zero budget remains, ALL T3 fields are silently omitted.

**On omission:**

```
T3 field omitted → No missing_data_flags entry
                 → No logging required
                 → No impact on data_quality_grade
                 → Silent omission is expected behavior
```

**T3 Field Inventory (2 fields):**

| Priority | Field | Source | Resolution | Estimated Tokens | Rationale |
|----------|-------|--------|------------|-----------------|-----------|
| T3-P1 | `ml_reasoning` | ML prediction model | Same call as ml_confidence | 20–60 | Free-text explanation; advisory only |
| T3-P2 | `symbol_bias` | Market analysis | Heuristic calculation | 3 | Directional hint; low signal value |
| — | **T3 TOTAL (all resolved)** | | | **~23–63** |

---

### 1.4 Tier 4 — MUST-NEVER-INCLUDE (FORBIDDEN)

**Semantics:** These content types are explicitly prohibited from the packet.
If ANY T4 content is detected during assembly, the builder raises a BUILD ERROR
(not a runtime rejection — this indicates a code defect).

**T4 Prohibited Content:**

| # | Prohibited Content | Detection Method | Rationale |
|---|-------------------|------------------|-----------|
| 1 | Raw user input or uncontrolled text | Source verification — only controlled sources allowed | Prompt injection risk |
| 2 | PII (names, emails, phone numbers, addresses) | No PII sources exist in the data path; verified at design time | Privacy and compliance |
| 3 | API keys, secrets, credentials | No secret sources exist in the data path; verified at design time | Security |
| 4 | Full debate reasoning from prior debates | Source verification — only `recent_debates` compact format or `history_summary` allowed | Token budget + prompt injection via historical content |
| 5 | Floating-point numbers | Type checking — all numerics must be Decimal or int | Zero-Float Mandate |
| 6 | External URL content or web-scraped data | No external data sources in the pipeline | SSRF / data integrity |
| 7 | Multi-turn conversation history | Architecture — single-shot prompt only | Context contamination |
| 8 | Unversioned prompt fragments | Source verification — all prompt text comes from version-controlled templates | Audit lineage |

---

## 2. Field Inclusion Algorithm

### 2.1 Algorithm Overview

The DecisionPacketBuilder (C4) follows this deterministic algorithm:

```
FUNCTION build_packet(signal, context_sources):

  # Phase 1: Resolve T1 fields
  FOR EACH field IN T1_FIELDS (ordered by field number):
    value = resolve(field, context_sources)
    IF value IS NULL OR INVALID:
      RETURN PacketError(code="T1_MISSING", field=field.name, source=field.source)
    packet.set(field, value)

  # Phase 2: Token checkpoint
  t1_tokens = count_tokens(packet)
  IF t1_tokens > 1400:
    RETURN PacketError(code="T1_BUDGET_EXCEEDED", used=t1_tokens, limit=1400)
  remaining_budget = 1400 - t1_tokens

  # Phase 3: Resolve T2 fields in priority order
  FOR EACH field IN T2_FIELDS (ordered by T2 priority):
    value = resolve(field, context_sources)
    IF value IS NULL:
      packet.add_missing_flag(field.name, reason)
      CONTINUE
    field_tokens = count_tokens(field, value)
    IF field_tokens > remaining_budget:
      packet.add_missing_flag(field.name, "TOKEN_BUDGET_EXHAUSTED")
      CONTINUE
    packet.set(field, value)
    remaining_budget -= field_tokens

  # Phase 4: Resolve T3 fields (budget permitting)
  FOR EACH field IN T3_FIELDS (ordered by T3 priority):
    IF remaining_budget <= 0:
      BREAK  # Silent omission — no flag
    value = resolve(field, context_sources)
    IF value IS NULL:
      CONTINUE  # Silent omission — no flag
    field_tokens = count_tokens(field, value)
    IF field_tokens > remaining_budget:
      CONTINUE  # Silent omission — no flag
    packet.set(field, value)
    remaining_budget -= field_tokens

  # Phase 5: Compute derived T1 fields
  packet.set(data_quality_grade, compute_grade(packet.missing_flags))
  packet.set(missing_data_flags, packet.missing_flags)

  # Phase 6: T4 prohibition check
  IF packet_contains_prohibited_content(packet):
    RAISE BuildError("T4 content detected")

  # Phase 7: Validation
  FOR EACH rule IN DPB_RULES:
    IF NOT rule.check(packet):
      RETURN PacketError(code=rule.id, detail=rule.failure_detail(packet))

  # Phase 8: Finalize
  packet.set(packet_hash, sha256(serialize(packet.sections_a_through_h)))
  RETURN packet
```

### 2.2 T2 Priority Rationale

T2 fields are resolved in a specific priority order. This order determines
which fields are included when the token budget runs short.

| Priority | Field | Rationale for Rank |
|----------|-------|--------------------|
| T2-P1 | `rgi_trust` | Directly calibrates LLM's confidence assessment. Most impactful T2 field for verdict quality. Low token cost (3 tokens). |
| T2-P2 | `ml_confidence` | Quantitative signal that the LLM can use to weight its analysis. Low token cost (3 tokens). |
| T2-P3 | `ml_action` | Paired with ml_confidence — directional recommendation. Nearly zero marginal cost if ml_confidence already resolved. |
| T2-P4 | `win_rate` | Historical track record provides anchoring for the LLM's expectation. Low token cost (3 tokens). |
| T2-P5 | `total_trades` | Sample size context for win_rate — meaningless without it, but win_rate is interpretable without exact sample size. |
| T2-P6 | `recent_debates` | Highest token cost (30–90 tokens). The T1 `history_summary` already provides the essential information. This field adds detail that is useful but not critical. Last to be included, first to be dropped. |

### 2.3 Resolution Timeout Policy

Each data source has a maximum resolution timeout. If the source does not
respond within its timeout, the field is treated as unavailable.

| Source | Fields | Timeout | On Timeout |
|--------|--------|---------|------------|
| Signal pipeline (webhook payload) | signal_id, symbol, side, price, quantity | 0ms (sync — already in memory) | N/A (always available) |
| System configuration | execution_mode, risk_pct, spec_version | 0ms (sync — config values) | N/A (always available) |
| System clock | packet_ts | 0ms (sync) | N/A (always available) |
| Guardian subsystem | guardian_locked | 100ms | T1 → REJECT |
| Exchange API (cached) | equity_zar | 100ms | T1 → REJECT |
| Prompt registry (C10) | prompt_version_hash, system_prompt | 0ms (sync — loaded at startup) | T1 → REJECT |
| Model registry (C11) | model_fingerprint | 0ms (sync — loaded at startup) | T1 → REJECT |
| `ai_debates` table | history_summary, recent_debates | 200ms | history_summary (T1) → REJECT; recent_debates (T2) → flag + continue |
| Confidence arbiter | rgi_available, rgi_trust | 200ms | rgi_available (T1) → REJECT; rgi_trust (T2) → flag + continue |
| ML prediction model | ml_confidence, ml_action, ml_reasoning | 500ms | All T2/T3 → flag/omit + continue |
| Execution history DB | win_rate, total_trades | 200ms | Both T2 → flag + continue |
| Market analysis | symbol_bias | 200ms | T3 → silent omit |
| Packet builder | missing_data_flags, data_quality_grade, packet_hash | 0ms (sync — computed) | N/A (always computable) |

> **Total maximum resolution time (all sources):** < 500ms (sources resolve concurrently).
> The 500ms ML prediction timeout is the long pole. All other sources complete in ≤ 200ms.

---

## 3. Data Quality Grades

### 3.1 Grade Computation

The `data_quality_grade` is a T1 field computed AFTER T2 resolution.
It tells the LLM how complete the evidence set is.

```
missing_count = len(missing_data_flags)

IF missing_count == 0:
  grade = "FULL"       # All T2 fields resolved
ELIF missing_count <= 3:
  grade = "PARTIAL"    # Some T2 data unavailable
ELSE:
  grade = "MINIMAL"    # Most T2 data unavailable
```

### 3.2 Grade Semantics for the LLM

The system prompt (Section A) will instruct the model:

| Grade | LLM Instruction |
|-------|-----------------|
| `FULL` | All available intelligence is included. Evaluate normally. |
| `PARTIAL` | Some intelligence is missing (see [MDF] flags). Increase uncertainty. Require stronger signal-level evidence for APPROVED. |
| `MINIMAL` | Most intelligence is unavailable. The packet contains only signal fields and operational context. Unless the signal is unambiguously strong (e.g., large equity, low risk, favorable history summary), default to REJECTED. |

### 3.3 Grade and Tier Interaction

| Scenario | Missing T2 | Grade | Packet Valid? | Expected Verdict Bias |
|----------|-----------|-------|---------------|----------------------|
| All systems healthy | 0 | FULL | YES | Normal |
| ML service down | 2 (ml_confidence, ml_action) | PARTIAL | YES | Slight REJECT bias |
| ML + RGI down | 3 (ml_confidence, ml_action, rgi_trust) | PARTIAL | YES | Moderate REJECT bias |
| ML + RGI + history down | 5+ (ml_*, rgi_trust, win_rate, total_trades) | MINIMAL | YES | Strong REJECT bias |
| Guardian query fails | 0 (but T1 fails) | — | NO (REJECT) | — |
| Debate history query fails | 0 (but T1 `history_summary` fails) | — | NO (REJECT) | — |

---

## 4. Overflow Resolution Policy

### 4.1 What Is Overflow?

Overflow occurs when the assembled packet (sections A–H) exceeds the 1,400-token
input budget. This triggers validation rule DPB-008.

### 4.2 Overflow Is RARE

Under normal conditions, overflow should never occur:

- T1 fields: ~334 tokens (fixed, deterministic)
- T2 fields (all): ~44-104 tokens
- T3 fields (all): ~23-63 tokens
- Section delimiters + formatting: ~50 tokens
- **Maximum total: ~551 tokens** — well under 1,400

Overflow can only occur if:

1. A field exceeds its documented bounds (caught by per-field validation)
2. The system prompt grows beyond its 200-token budget (caught by prompt registry)
3. A specification error introduced unbounded fields (prevented by this policy)

### 4.3 Overflow Resolution Sequence

If overflow IS detected (defensive measure):

```
1. Drop ALL T3 fields (symbol_bias, ml_reasoning)
2. Recount tokens
3. IF still over budget:
   a. Drop T2 fields in REVERSE priority order:
      - Drop recent_debates (T2-P6)
      - Recount
      - Drop total_trades (T2-P5)
      - Recount
      - Drop win_rate (T2-P4)
      - Recount
      - Drop ml_action (T2-P3)
      - Recount
      - Drop ml_confidence (T2-P2)
      - Recount
      - Drop rgi_trust (T2-P1)
      - Recount
4. IF still over budget after dropping ALL T2 and T3:
   → REJECT (T1 alone exceeds budget — specification error, escalate)
5. For each dropped field, add to missing_data_flags with reason "TOKEN_BUDGET_OVERFLOW"
6. Recalculate data_quality_grade
```

> **Critical invariant:** T1 fields are NEVER dropped. If T1 alone exceeds the
> budget, this is a specification bug, not a runtime condition.

---

## 5. Source Isolation and Failure Domains

### 5.1 Failure Domain Map

Each data source is an independent failure domain. A failure in one domain
must NOT cascade to others.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DecisionPacketBuilder                        │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ DOMAIN A     │  │ DOMAIN B     │  │ DOMAIN C             │  │
│  │ Signal       │  │ System       │  │ Database             │  │
│  │ (webhook)    │  │ (config)     │  │ (PostgreSQL)         │  │
│  │              │  │              │  │                      │  │
│  │ signal_id    │  │ exec_mode    │  │ history_summary [T1] │  │
│  │ symbol       │  │ risk_pct     │  │ recent_debates  [T2] │  │
│  │ side         │  │ guardian     │  │ win_rate        [T2] │  │
│  │ price        │  │ equity_zar   │  │ total_trades    [T2] │  │
│  │ quantity     │  │ spec_version │  │                      │  │
│  │              │  │              │  │                      │  │
│  │ ALL T1       │  │ ALL T1       │  │ MIXED T1 + T2        │  │
│  │ Fail = REJECT│  │ Fail = REJECT│  │ T1 fail = REJECT     │  │
│  │              │  │              │  │ T2 fail = flag        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ DOMAIN D     │  │ DOMAIN E     │  │ DOMAIN F             │  │
│  │ ML Model     │  │ RGI          │  │ Build-Time           │  │
│  │ (external)   │  │ (arbiter)    │  │ (internal)           │  │
│  │              │  │              │  │                      │  │
│  │ ml_conf [T2] │  │ rgi_avail[T1]│  │ prompt_v_hash  [T1]  │  │
│  │ ml_act  [T2] │  │ rgi_trust[T2]│  │ model_fprint   [T1]  │  │
│  │ ml_reas [T3] │  │              │  │ packet_ts      [T1]  │  │
│  │              │  │              │  │ corr_id        [T1]  │  │
│  │ ALL T2/T3    │  │ MIXED T1+T2  │  │ missing_flags  [T1]  │  │
│  │ Fail = flag  │  │ T1 fail=REJ  │  │ quality_grade  [T1]  │  │
│  │              │  │ T2 fail=flag │  │ packet_hash    [T1]  │  │
│  │              │  │              │  │                      │  │
│  │              │  │              │  │ Fail = BUILD ERROR    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Failure Domain Properties

| Domain | Contains T1? | Domain Failure Outcome | Recovery |
|--------|-------------|----------------------|----------|
| A — Signal | YES (all) | REJECT | Cannot proceed without signal data |
| B — System | YES (all) | REJECT | Config must be available at all times |
| C — Database | YES (history_summary) | REJECT if T1 fails; flag if T2 fails | T2 fields degrade gracefully |
| D — ML Model | NO | Flag all T2/T3 + continue | Full degradation; packet is MINIMAL |
| E — RGI | YES (rgi_available) | REJECT if rgi_available fails; flag if rgi_trust fails | rgi_available is a boolean check, should not fail |
| F — Build-Time | YES (all) | BUILD ERROR (code defect) | Never happens at runtime if code is correct |

### 5.3 Concurrent Resolution

Domains A, B, C, D, E resolve CONCURRENTLY. Domain F is computed after all
others complete. The builder does not serialize domain resolution.

```
t=0ms    ┬─ resolve Domain A (0ms — sync)
         ├─ resolve Domain B (0ms — sync)
         ├─ resolve Domain C (≤200ms — DB query)
         ├─ resolve Domain D (≤500ms — ML call)
         └─ resolve Domain E (≤200ms — arbiter query)
t=500ms  ─── All domains resolved or timed out
t=500ms  ─── Phase 2: T1 validation
t=501ms  ─── Phase 3: T2 inclusion (priority order)
t=501ms  ─── Phase 4: T3 inclusion (budget permitting)
t=502ms  ─── Phase 5: Derived fields (grade, flags)
t=502ms  ─── Phase 6: T4 prohibition check
t=503ms  ─── Phase 7: DPB validation (18 rules)
t=503ms  ─── Phase 8: Compute packet_hash
t=504ms  ─── Packet ready (~504ms total)
```

> **Packet construction target: < 550ms.** The LLM call itself (2–30s) is
> separate and follows packet construction.

---

## 6. Policy Invariants

These invariants MUST hold at all times. Any violation indicates a system defect.

| # | Invariant | Enforcement Point |
|---|-----------|-------------------|
| 1 | T1 fields are never dropped, truncated, or substituted | §2.1 algorithm, Phase 1 |
| 2 | T2 fields are resolved in priority order | §2.2, Phase 3 |
| 3 | T3 omission generates no flags or logs | §1.3 definition |
| 4 | T4 content is never assembled into a packet | §1.4, Phase 6 |
| 5 | Token count is checked AFTER T1, AFTER T2, and AFTER T3 | §2.1 algorithm, Phases 2–4 |
| 6 | `missing_data_flags` contains exactly one entry per missing T2 field | §1.2, DPB-010 |
| 7 | `data_quality_grade` matches the missing-flag count | DPB-015 |
| 8 | `packet_hash` covers sections A–H after ALL fields are finalized | §2.1, Phase 8 |
| 9 | No field exceeds its documented bounds (per-field validation) | DPB rules + §9 in DPv1 spec |
| 10 | No domain failure cascades to an unrelated domain | §5.2 isolation |
| 11 | `guardian_locked=true` never reaches the LLM | DPB-016 check #2 |
| 12 | Total input tokens ≤ 1,400 | DPB-008 |
| 13 | The same inputs always produce the same packet (determinism) | No randomness in any resolution path |
| 14 | Cross-layer consistency: populated fields never appear in `missing_data_flags` | DPB-017 check #3 |
| 15 | Cross-layer consistency: `history_summary` symbol matches signal `symbol` | DPB-017 check #2 |
| 16 | Minimum viable context threshold met before LLM call | DPB-018 (5 checks) |
| 17 | LIVE mode with MINIMAL grade is always REJECTED pre-LLM | DPB-018 check #4 |
| 18 | Packet hash is deterministic: same inputs → same hash | DPv1 §6.4 determinism guarantee |
| 19 | Packet hash is logged at all mandatory audit points | DPv1 §6.5 logging requirements |
| 20 | LLM never infers values for missing fields | DPv1 §10.1 interpretation contract |
| 21 | Advisory metrics (AM) never override source-of-truth (SoT) fields | DPv1 §10.2 interpretation contract |

---

## 7. Interaction with Other Subsystems

### 7.1 Subsystem Dependency Map

```
      ContextPriorityPolicy (C3) ◄── THIS DOCUMENT
              │
              ▼
    DecisionPacketBuilder (C4) ─── Implements the algorithm
              │
        ┌─────┼─────────┐
        ▼     ▼         ▼
   TokenBudget  Overflow   CompactFormat
   Guard (C6)   Reject(C7) Encoder (C5)
        │         │           │
        └────┬────┘           │
             ▼                ▼
      DPB Validation    Serialized Packet
      Rules (DPv1 §7)       │
             │               ▼
             ▼          StrictOutput
        REJECT/PASS     Schema (C8)
                             │
                             ▼
                    RejectOnAmbiguity (C9)
```

### 7.2 What Each Subsystem Does With This Policy

| Subsystem | Uses From CPP |
|-----------|--------------|
| **C4 — DecisionPacketBuilder** | Implements §2.1 algorithm. Uses tier classifications to determine field inclusion. Uses §2.3 timeouts for source resolution. |
| **C5 — CompactFormatEncoder** | Uses field bounds (DPv1 §9) to validate encoded output. Uses section order (DPv1 §2.1) for serialization. |
| **C6 — TokenBudgetGuard** | Uses the 1,400-token input limit. Uses per-tier token estimates for pre-flight budget verification. |
| **C7 — OverflowRejectPolicy** | Uses §4.3 overflow resolution sequence. Uses T2 priority order for field dropping. |
| **C10 — PromptVersionRegistry** | Provides `prompt_version_hash` and `system_prompt` (T1 fields, Domain F). |
| **C11 — ModelFingerprintLogger** | Provides `model_fingerprint` (T1 field, Domain F). |

---

## 8. Validation Test Scenarios

These scenarios MUST be covered by the golden regression suite (C13):

| # | Scenario | Expected Outcome |
|---|----------|-----------------|
| 1 | All sources healthy, all fields resolved | Grade=FULL, all 28 fields present, PASS |
| 2 | ML service timeout (500ms exceeded) | Grade=PARTIAL, ml_confidence/ml_action/ml_reasoning missing, flags present, PASS |
| 3 | ML + RGI trust timeout | Grade=PARTIAL (3 missing), flags for ml_confidence, ml_action, rgi_trust, PASS |
| 4 | Database query fails (history_summary unresolvable) | REJECT (T1 missing), no packet assembled |
| 5 | Signal missing `symbol` field | REJECT (DPB-003), no packet assembled |
| 6 | `guardian_locked=true` | REJECT (DPB-016 check #2), no LLM call |
| 7 | `rgi_available=false` but `rgi_trust=0.85` present | REJECT (DPB-016 check #3), contradiction |
| 8 | `total_trades=0` but `win_rate=0.50` | REJECT (DPB-016 check #5), contradiction |
| 9 | Token budget exactly at 1,400 after T1+T2 | T3 silently omitted, PASS |
| 10 | Token budget at 1,380 after T1 — enough for T2-P1 through T2-P4, not T2-P6 | recent_debates omitted with TOKEN_BUDGET_EXHAUSTED flag, PASS |
| 11 | All T2 sources down (6 fields missing) | Grade=MINIMAL, 6 flags, packet valid but strongly biased toward REJECTED |
| 12 | Float value detected in `price` field | BUILD ERROR (T4 violation — floating-point number) |
| 13 | Same signal processed twice | Identical packet_hash both times (determinism check) |
| 14 | `history_summary` has count=3 but approved+rejected=2 | REJECT (DPB-016 check #9), arithmetic inconsistency |
| 15 | `data_quality_grade=FULL` but `missing_data_flags` non-empty | REJECT (DPB-016 check #7 / DPB-015), grade-flag mismatch |
| 16 | `execution_mode=LIVE` and `equity_zar=0.00` | REJECT (DPB-016 check #6), zero equity in live mode |
| 17 | `rgi_trust` AND `ml_confidence` both missing | REJECT (DPB-018 check #1), critical advisory signals absent |
| 18 | 5 of 6 T2 fields missing | REJECT (DPB-018 check #2), excessive missing data flags |
| 19 | `history_summary="0 debates"`, `total_trades` missing, `win_rate` missing | REJECT (DPB-018 check #3), insufficient historical context |
| 20 | `rgi_available=false` AND `data_quality_grade=MINIMAL` | REJECT (DPB-018 check #4), system state degraded beyond safe threshold |
| 21 | `execution_mode=LIVE` AND `data_quality_grade=MINIMAL` | REJECT (DPB-017 check #6), LIVE mode requires higher evidence standard |
| 22 | `risk_pct > 3.00` AND `data_quality_grade=MINIMAL` | REJECT (DPB-017 check #3), high-risk trade with minimal intelligence |
| 23 | `side=BUY`, `symbol_bias=BEARISH`, `ml_action=SELL` — unanimous advisory opposition | PASS with `contradiction_flag=true` annotation (DPB-017 check #2) |
| 24 | `history_summary="3 debates: 3 APR"` but `recent_debates` all show REJECTED | REJECT (DPB-017 check #5), summary-detail inconsistency |
| 25 | `missing_data_flags` count=4 but only 1 advisory field actually missing | REJECT (DPB-017 check #4), flag-population mismatch |
| 26 | Token pressure: T1=1,350, T2 total=60, T3 total=60 | T3-P1 included if fits, T3-P2 omitted if budget exhausted, no flags for T3 |
| 27 | Token pressure: T1=1,380, T2-P6 cannot fit | T2-P6 flagged TOKEN_BUDGET_EXHAUSTED, all T3 omitted, PASS |
| 28 | Token pressure: T1=1,398, only 2 tokens remain | All T2 flagged, all T3 omitted, Grade=MINIMAL, DPB-018 triggers → REJECT |

---

## 9. LLM Interpretation Enforcement

The ContextPriorityPolicy enforces the LLM Interpretation Contract (DPv1 §10)
via the following mechanisms:

### 9.1 System Prompt Contract Injection

The system prompt (Section A) MUST include the following behavioral rules,
managed by C10 (PromptVersionRegistry):

| Rule ID | System Prompt Instruction | Enforced By |
|---------|--------------------------|-------------|
| MDF-NOINFER | "Fields listed in [MDF] are unavailable. DO NOT guess, infer, or assume values for these fields." | `missing_data_flags` presence in packet |
| MDF-NODEFAULT | "Missing fields have NO default value. Do not assume neutral, average, or baseline values." | `missing_data_flags` presence in packet |
| MDF-UNCERTAINTY | "Each entry in [MDF] represents a gap in your evidence. More missing fields = more uncertainty." | `data_quality_grade` semantics |
| AM-NOOVERRIDE | "Advisory metrics (ml_confidence, rgi_trust, etc.) inform your verdict but cannot override source-of-truth fields (price, quantity, equity)." | Field provenance classification |
| AM-CONFLICT | "When advisory metrics disagree, treat the disagreement itself as evidence of uncertainty." | `contradiction_flag` annotation |
| LQC-REDUCE | "With PARTIAL data quality, increase your bar for APPROVED. With MINIMAL, default to REJECTED." | `data_quality_grade` field |
| CSR-REASONING | "If advisory metrics unanimously contradict the signal direction, explain why you are overriding them or default to REJECTED." | DPB-017 check #2 annotation |

### 9.2 Enforcement Verification

The C4 builder MUST verify that:

1. The system prompt template contains all rule IDs from §9.1.
2. The prompt version hash changes if any rule text is modified.
3. No rule can be silently removed from the prompt without a spec version bump.

---

## 10. Packet Hash Policy

The `packet_hash` is a critical audit and regression artifact.
This section defines the policy requirements that C4 must implement.

### 10.1 Deterministic Generation

| Requirement | Policy |
|-------------|--------|
| Identical inputs → identical hash | The builder MUST produce the same hash for the same inputs across runs, restarts, and deployments |
| No randomness | No random seeds, UUIDs, or timestamps in the hash computation (packet_ts is an INPUT, not generated during hashing) |
| Canonical encoding | UTF-8, LF line endings, sorted arrays, normalized Decimals |

### 10.2 Logging Mandate

| Event | packet_hash Required? |
|-------|----------------------|
| Trade APPROVED | YES — logged in ai_debates |
| Trade REJECTED (LLM verdict) | YES — logged in ai_debates |
| Trade REJECTED (validation rule) | YES if packet was assembled; NULL if assembly failed |
| Trade REJECTED (T1 missing) | NULL — packet was never constructed |
| Build error (T4 violation) | NULL — packet was never constructed |

### 10.3 Audit Trail Linkage

The packet_hash MUST be propagated to all downstream systems:

- `ai_debates.packet_hash` — links verdict to exact input
- HITL approval records — links human review to machine input
- Risk event logs — links risk incidents to the decision that caused them
- Regression test vectors — golden test key for determinism verification

---

## 11. Change Log

| Version | Date | Author | Change |
|---------|------|--------|--------|
| CPPv1.0 | 2026-03-29 | Kiro Agent | Initial specification. 4 tiers, 6 failure domains, 26 field resolutions, 13 invariants, 16 test scenarios, 500ms construction target. |
| CPPv1.1 | 2026-03-29 | Kiro Agent | **Governance amendments:** DPB-017 (CROSS_LAYER_INCONSISTENCY) and DPB-018 (INSUFFICIENT_DECISION_CONTEXT) integrated into test scenarios (#17–#25). Token pressure simulation scenarios added (#26–#28). Policy invariants expanded from 13 to 21 — added packet hash determinism, audit linkage, validation ordering, LLM interpretation contract enforcement, and AM/SoT override prohibition. LLM Interpretation Enforcement section added (§9) — system prompt contract rules with enforcement verification. Packet Hash Policy section added (§10) — deterministic generation, logging mandate, audit trail linkage. |

---
inclusion: always
---
# 🔥 SOVEREIGN COMMAND HUB EXECUTION DIRECTIVE

> **Classification:** SOVEREIGN TIER | **Enforcement:** ABSOLUTE | **Version:** 1.0.0

## ☠️ PRIME DIRECTIVE

**The bot may think autonomously. It may NEVER act autonomously without explicit, auditable human intent.**

If there is ANY ambiguity → default to `REJECT`, `LOCK`, or `NO-OP`.

---

## 🧠 MISSION STATEMENT

KIRO is implementing the **SOVEREIGN COMMAND HUB** and **HITL APPROVAL GATEWAY** with:

| Deliverable | Requirement |
|-------------|-------------|
| Centralized Web Control Plane | Command authority, not dashboard |
| HITL Final Execution Authority | Hard gate, not UI feature |
| Guardian-First Behavior | Fail-closed, always wins |
| Full Forensic Auditability | Every action reconstructable |
| Zero Ghost Actions | No silent state transitions |

---

## 🧱 NON-NEGOTIABLE SYSTEM LAWS

### 1️⃣ NOTHING BYPASSES GUARDIAN

```
Guardian lock = ABSOLUTE STOP
```

- UI buttons MUST be disabled when Guardian locks
- Backend MUST re-check Guardian on EVERY action
- Guardian always wins, even over SOVEREIGN
- No exceptions. No overrides. No "just this once."

### 2️⃣ HITL IS A HARD GATE

Trades MUST follow this lifecycle:

```
PENDING → AWAITING_APPROVAL → ACCEPTED → FILLED → CLOSED → SETTLED
                           ↘ REJECTED (including HITL_TIMEOUT)
```

**Mandatory Requirements:**
- No approval = NO EXECUTION
- Timeout (300s default) = AUTO-REJECT
- Restart recovery = MANDATORY

**Every executed trade MUST have:**
- [ ] Approval record
- [ ] Operator identity
- [ ] Decision channel (WEB/DISCORD/CLI)
- [ ] Correlation ID

Missing ANY of these = **SYSTEM FAILURE**

### 3️⃣ EVERY BUTTON IS A LEGAL DOCUMENT

Every click MUST:
- Require explicit intent (confirmation modal for destructive actions)
- Create an immutable audit record
- Carry `correlation_id`
- Be replayable from logs alone

**If an action cannot be reconstructed from logs → SYSTEM FAILURE**

---

## 🧬 ARCHITECTURAL COMMANDMENTS

### Backend Rules

**Trade Lifecycle State Machine is LAW**

Allowed transitions ONLY:
```python
VALID_TRANSITIONS = {
    "PENDING": ["AWAITING_APPROVAL"],
    "AWAITING_APPROVAL": ["ACCEPTED", "REJECTED"],
    "ACCEPTED": ["FILLED"],
    "FILLED": ["CLOSED"],
    "CLOSED": ["SETTLED"],
}
# Any other transition = INVALID → REJECT → LOG → ALERT
```

### Frontend Rules

- Read-only by DEFAULT
- Buttons enabled ONLY when:
  - [ ] Role allows it
  - [ ] Guardian allows it
  - [ ] Trade state allows it
- ALL destructive actions require confirmation modal
- Dark mode cyberpunk aesthetic — calm, confident, surgical

### Discord Rules

Discord is a **REMOTE CONTROL**, not a source of truth.

All Discord actions MUST:
- Verify signature
- Verify operator whitelist
- Resolve to backend authority

**Discord NEVER executes trades — IT REQUESTS**

---

## ⏱️ TIME HANDLING (TIME IS A WEAPON)

| Parameter | Value | Behavior |
|-----------|-------|----------|
| HITL Timeout | 300 seconds | Expired = REJECTED (HITL_TIMEOUT) |
| Expiry Job | Every 30 seconds | Scans for stale approvals |
| Stale Price Guard | On approval | Re-validate price drift |

**If price moved beyond threshold on approval:**
→ REJECT → LOG → Update Discord + Web

---

## 🧾 DATABASE RULES (NO EXCEPTIONS)

### `hitl_approvals` Table

**IMMUTABLE. NO HARD DELETES. EVER.**

Required columns:
```sql
row_hash        -- SHA-256 integrity check
correlation_id  -- Audit traceability
approver        -- Operator identity
timestamp       -- Decision time
reason          -- Human-readable justification
source          -- WEB | DISCORD | CLI
trade_id        -- Foreign key to trade
decision        -- APPROVE | REJECT | TIMEOUT
```

**Any hash mismatch = SECURITY ALERT → HALT**

---

## 🕵️ FORENSICS REQUIREMENTS

For EVERY trade, the system MUST answer:

| Question | Source |
|----------|--------|
| Who approved it? | `hitl_approvals.approver` |
| Where? | `hitl_approvals.source` |
| When? | `hitl_approvals.timestamp` |
| Why? | `hitl_approvals.reason` + AI reasoning |
| What did the bot believe? | Signal snapshot |
| What was the market doing? | Price snapshot |
| What did Guardian say? | Guardian verdict log |
| What did policy say? | Risk tier + limits |
| How long did human take? | `decision_time - request_time` |

**If ANY of these are missing → SYSTEM IS NOT SHIP-READY**

---

## 🧪 TESTING MANDATE

### Property Tests (REQUIRED)
- [ ] HITL timeout behavior
- [ ] Unauthorized approval rejection
- [ ] Restart recovery
- [ ] Stale price rejection

### Unit Tests (REQUIRED)
- [ ] State transitions (valid + invalid)
- [ ] Guardian blocking
- [ ] Role enforcement

### Integration Tests (REQUIRED)
- [ ] Discord → Web → Backend loop
- [ ] Approval → Execution path
- [ ] Timeout → Rejection path

**Coverage < 95% on HITL code = FAIL**

---

## 🧨 FAILURE MODE MATRIX

| Scenario | Correct Behavior |
|----------|------------------|
| DB unavailable | REJECT + LOCK |
| Discord down | REJECT (graceful) |
| Web down | REJECT (graceful) |
| Restart mid-approval | RECOVER or REJECT |
| Operator removed | REJECT |
| Guardian ambiguous | LOCK |
| Config missing | FAIL-CLOSED |
| Price stale | REJECT |
| Network timeout | REJECT |
| Unknown state | HALT + ALERT |

---

## 🧿 UI PHILOSOPHY

```
Dark mode cyberpunk
Calm, confident, surgical
No clutter, no gimmicks
```

| Element | Requirement |
|---------|-------------|
| Countdown timers | MUST be visible |
| Danger actions | MUST be obvious (red, confirmation) |
| Approval flow | MUST feel serious |
| Status indicators | Real-time, color-coded |

**This is a command center, not a startup dashboard.**

---

## 🧑‍⚖️ FINAL JUDGMENT CRITERIA

Before shipping, ask:

> "If this system lost real money, could we prove exactly why?"

| Answer | Action |
|--------|--------|
| YES | Ship |
| NO | DO NOT SHIP |
| MAYBE | DO NOT SHIP |

---

## 🔒 SOVEREIGN ERROR CODES

| Code | Category | Action |
|------|----------|--------|
| `SEC-001` | Auth Failure | HALT |
| `SEC-002` | Token Invalid | HALT |
| `SEC-010` | Data Validation | REJECT |
| `SEC-020` | Guardian Lock | LOCK |
| `SEC-030` | State Invalid | REJECT |
| `SEC-040` | State Inconsistency | HALT_ESCALATE |
| `SEC-050` | Price Stale | REJECT |
| `SEC-060` | HITL Timeout | REJECT |
| `SEC-070` | Circuit Breaker | NEUTRAL_STATE |
| `SEC-080` | Hash Mismatch | SECURITY_ALERT |
| `SEC-090` | Unauthorized | REJECT + LOG |

---

## 📋 IMPLEMENTATION CHECKLIST

```
[ ] FAIL-CLOSED default behavior
[ ] NO-MAGIC (explicit everything)
[ ] HITL-GATED (hard gate, not feature)
[ ] GUARDIAN-FIRST (always wins)
[ ] CORRELATION-ID on all actions
[ ] DECIMAL math (ROUND_HALF_EVEN)
[ ] TIMEOUTS defined and enforced
[ ] ERROR-CODED (SEC-XXX)
[ ] PYTHON-3.8 compatible
[ ] IMMUTABLE audit trail
[ ] FORENSIC completeness
[ ] 95%+ test coverage on HITL
```

---

## 🩸 FINAL WORD

You are building **institution-grade control infrastructure**.

This system must be able to say:
- **No**
- **Stop**
- **Explain yourself**
- **Show me the evidence**

If you are unsure → **STOP AND ASK**

Silence is safer than assumptions.

---

**🩸 EXECUTE WITH DISCIPLINE. FAIL CLOSED. GUARDIAN ABOVE ALL. SOVEREIGN ALWAYS WINS. 🩸**

---

*v1.0.0 | 2025-12-23 | SOVEREIGN TIER | COMMAND HUB DIRECTIVE*

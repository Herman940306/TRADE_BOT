# First Live Trade Checklist — Autonomous Alpha

**Version:** 1.0.0
**Phase:** 4 — Operational Funding & First Live Trade Readiness
**Date:** 2025-07-27

---

## Purpose

Strict go/no-go checklist for executing the very first real-money trade on VALR. Every checkbox must be checked before enabling `EXECUTION_MODE=LIVE`. If any item fails, STOP and resolve before continuing.

> **Mandate:** Survival > Capital Preservation > Alpha.
> A skipped checkbox is an uncontrolled risk.

---

## Prerequisites

These runbooks must be fully completed before starting this checklist:

- [ ] `DOCS/VALR_ONBOARDING_CHECKLIST.md` — COMPLETE
- [ ] `DOCS/FUNDING_RUNBOOK.md` — COMPLETE (funds confirmed on VALR)
- [ ] `DOCS/PRODUCTION_ENV_REQUIREMENTS.md` — READ AND UNDERSTOOD

---

## Gate 1: Credentials & Connectivity

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 1.1 | VALR API key is set in `.env` | `grep VALR_API_KEY .env` shows non-placeholder value | [ ] |
| 1.2 | VALR API secret is set in `.env` | `grep VALR_API_SECRET .env` shows non-placeholder value | [ ] |
| 1.3 | API key has View + Trade permissions (NOT Withdraw) | Verify in VALR dashboard → API Keys | [ ] |
| 1.4 | Connectivity check passes | `python scripts/check_exchange_connectivity.py` → 5/5 PASS | [ ] |
| 1.5 | `.env` is NOT tracked by git | `git status .env` → untracked or ignored | [ ] |

---

## Gate 2: Balance Verification

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 2.1 | ZAR balance is visible | Connectivity check shows ZAR > 0 | [ ] |
| 2.2 | Balance matches your deposit | VALR dashboard ZAR available = expected amount | [ ] |
| 2.3 | `ZAR_FLOOR` matches funded amount | `grep ZAR_FLOOR .env` matches your deposit | [ ] |
| 2.4 | `MAX_ORDER_ZAR` is ≤ R500 | `grep MAX_ORDER_ZAR .env` shows 500 or less | [ ] |
| 2.5 | `MAX_RISK_ZAR` is ≤ R500 | `grep MAX_RISK_ZAR .env` shows 500 or less | [ ] |

---

## Gate 3: Safety Systems

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 3.1 | HITL is enabled | `grep HITL_ENABLED .env` → `true` | [ ] |
| 3.2 | HITL operator is configured | `grep HITL_ALLOWED_OPERATORS .env` → non-empty | [ ] |
| 3.3 | Guardian is unlocked | `curl -s http://localhost:8080/guardian/status` → `locked: false` | [ ] |
| 3.4 | Guardian reset code is saved securely | You can produce it from your password manager | [ ] |
| 3.5 | Guardian admin token is saved securely | You can produce it from your password manager | [ ] |
| 3.6 | Kill switch is enabled | `grep KILL_SWITCH_ENABLED .env` → `true` | [ ] |
| 3.7 | Kill switch script is accessible | `ls scripts/kill_switch.py` exists | [ ] |

---

## Gate 4: Mode Configuration

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 4.1 | Currently in LIVE_READ_ONLY mode | `grep EXECUTION_MODE .env` → `LIVE_READ_ONLY` | [ ] |
| 4.2 | LIVE_TRADING_CONFIRMED is NOT set yet | `grep LIVE_TRADING_CONFIRMED .env` → commented out or empty | [ ] |
| 4.3 | Readiness check passes | `python scripts/check_live_readiness.py` → all relevant checks pass | [ ] |
| 4.4 | Dry validation passes | `python scripts/validate_live_path.py` → 32/32 pass | [ ] |

---

## Gate 5: Application Health

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 5.1 | Docker stack is running | `docker compose -f docker-compose.local.yml ps` → all services up | [ ] |
| 5.2 | Health endpoint responds | `curl -s http://localhost:8080/` → `status: operational` | [ ] |
| 5.3 | Database is healthy | Health response shows `database: healthy` | [ ] |
| 5.4 | No pending HITL approvals | `curl -s http://localhost:8080/api/hitl/pending` → empty list | [ ] |

---

## Gate 6: Symbol & Price Review

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 6.1 | Target trading pair confirmed | You know which pair (e.g., `BTCZAR`) | [ ] |
| 6.2 | Current market price reviewed | Check VALR dashboard for current bid/ask | [ ] |
| 6.3 | Order size sensible | Your order in ZAR is ≤ `MAX_ORDER_ZAR` (R500) | [ ] |
| 6.4 | Spread is reasonable | Spread < 2% (`MARKET_DATA_MAX_SPREAD_PCT`) | [ ] |

---

## Gate 7: Rollback Preparation

| # | Check | Command / How to Verify | Pass? |
|---|---|---|---|
| 7.1 | You know how to stop the system | `docker compose -f docker-compose.local.yml down` | [ ] |
| 7.2 | You know how to trigger kill switch | `python scripts/kill_switch.py` | [ ] |
| 7.3 | You know how to revert to PAPER | Change `.env`: `EXECUTION_MODE=DEMO`, restart stack | [ ] |
| 7.4 | You know how to cancel an order on VALR | VALR dashboard → Open Orders → Cancel | [ ] |
| 7.5 | You have VALR dashboard open in your browser | Ready for manual verification | [ ] |

---

## FINAL GO/NO-GO DECISION

**Count your results:**

| Gate | Items | All Pass? |
|---|---|---|
| Gate 1: Credentials | 5 | [ ] |
| Gate 2: Balance | 5 | [ ] |
| Gate 3: Safety | 7 | [ ] |
| Gate 4: Mode | 4 | [ ] |
| Gate 5: Health | 4 | [ ] |
| Gate 6: Symbol | 4 | [ ] |
| Gate 7: Rollback | 5 | [ ] |
| **TOTAL** | **34** | **[ ]** |

> **If ANY gate has a failing item: STOP. Do not proceed. Fix the issue first.**

---

## Enable Live Trading

Only after ALL 34 checks pass:

### Step 1: Update `.env`

```env
EXECUTION_MODE=LIVE
LIVE_TRADING_CONFIRMED=TRUE
```

### Step 2: Restart the stack

```bash
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up -d
```

### Step 3: Verify startup

```bash
docker compose -f docker-compose.local.yml logs -f bot 2>&1 | head -50
```

Look for: `[STARTUP] Live mode prerequisites verified | mode=LIVE | checks_passed=OK`

If you see `[STARTUP-BLOCK]`, one or more prerequisites are missing. Read the error message, fix the issue, and restart.

### Step 4: The system is now live

- Orders will require HITL approval before execution
- Monitor the logs and your VALR dashboard
- Proceed to the trade signal flow (webhook → approval → execution)

### Step 5: After the trade

- Proceed immediately to `DOCS/POST_TRADE_REVIEW.md`

---

## Emergency Procedures

| Situation | Action |
|---|---|
| Order placed but unwanted | Cancel via VALR dashboard immediately |
| System behaving unexpectedly | `docker compose -f docker-compose.local.yml down` |
| Guardian locked the system | Expected after daily loss limit — use `GUARDIAN_RESET_CODE` only after review |
| Multiple orders placed | Kill switch: `python scripts/kill_switch.py` |
| Want to return to paper mode | Set `EXECUTION_MODE=DEMO` in `.env`, restart stack |

---

```
[Sovereign Reliability Audit]
- Classification: GO/NO-GO CHECKLIST (no code, no secrets)
- Gates: 7, Total checks: 34
- Minimum prerequisites: 3 completed runbooks
- Fail-safe: Any single failed check blocks progression
- GitHub Data Sanitization: [Safe for Public — no credentials or account data]
- Traceability: [correlation_id: PHASE4-FIRST-TRADE-001]
```

---

*FIRST_LIVE_TRADE_CHECKLIST.md v1.0.0 | Phase 4 | 2025-07-27 | SOVEREIGN TIER*

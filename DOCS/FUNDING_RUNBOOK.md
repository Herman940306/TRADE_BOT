# Funding Runbook — Autonomous Alpha

**Version:** 1.0.0
**Phase:** 4 — Operational Funding & First Live Trade Readiness
**Date:** 2025-07-27

---

## Purpose

Step-by-step guide for depositing funds into your VALR exchange account and verifying the balance is visible to the Autonomous Alpha system. This runbook is designed for a first-time deposit scenario with a small test amount.

> **Mandate:** Survival > Capital Preservation > Alpha.
> Start with the smallest amount that allows a meaningful test trade.

---

## Prerequisites

Before starting this runbook, you MUST have completed:

- [ ] `DOCS/VALR_ONBOARDING_CHECKLIST.md` — Account created, KYC approved, 2FA enabled, API credentials generated
- [ ] `DOCS/PRODUCTION_ENV_REQUIREMENTS.md` — All required env vars understood
- [ ] `.env` file populated with credentials (from `.env.live.example`)
- [ ] Connectivity verified via `scripts/check_exchange_connectivity.py` in LIVE_READ_ONLY mode

---

## Section 1: Determine Your Test Amount

Your first deposit should be small enough that losing it entirely would not matter.

| Guideline | Recommendation |
|---|---|
| Minimum practical amount | R500 ZAR |
| Recommended first deposit | R1,000 – R2,000 ZAR |
| Absolute maximum for first test | R5,000 ZAR |
| `MAX_ORDER_ZAR` setting | R500 (limits single order) |
| Daily loss limit (Guardian 1%) | 1% of `ZAR_FLOOR` |

> **Example:** If you deposit R2,000 and set `ZAR_FLOOR=2000.00`, Guardian will lock the system after R20 of daily losses. This is correct and desired for initial testing.

**Decide your amount now:** R_______ ZAR

---

## Section 2: Deposit ZAR to VALR

- [ ] 2.1 Log in to [https://www.valr.com](https://www.valr.com) with 2FA
- [ ] 2.2 Navigate to **Wallets** → **ZAR** (or the Deposit section)
- [ ] 2.3 Select **Deposit ZAR** (EFT / bank transfer)
- [ ] 2.4 VALR will display bank account details — note these carefully:
  - Bank name
  - Account number
  - Branch code
  - Reference (VALR assigns a unique reference — you MUST use it)
- [ ] 2.5 Log in to your personal bank (FNB, Standard Bank, Capitec, etc.)
- [ ] 2.6 Create a new payment/transfer to the VALR bank account
- [ ] 2.7 Enter the **exact reference** VALR provided — this is how they match the deposit to your account
- [ ] 2.8 Transfer your chosen amount (R_______ ZAR)
- [ ] 2.9 Confirm the transfer in your banking app

> **Note:** VALR also supports instant deposits via certain banks. Check their current deposit methods. EFT deposits may take 1-3 business days to clear.

---

## Section 3: Wait for Deposit Confirmation

- [ ] 3.1 Monitor your VALR account for the deposit to appear
- [ ] 3.2 VALR may send an email notification when funds arrive
- [ ] 3.3 Check your ZAR balance on the VALR dashboard:
  - Navigate to **Wallets** → **ZAR**
  - Confirm the **Available** balance matches your deposit amount
- [ ] 3.4 Record the confirmed amount: R_______ ZAR available

> **Important:** Do NOT proceed until the deposit is confirmed and shows as "Available" (not "Pending").

---

## Section 4: Update `.env` with Funded Equity

Now that you know your exact funded amount, update the system configuration:

- [ ] 4.1 Open your `.env` file
- [ ] 4.2 Set `ZAR_FLOOR` to your exact funded amount:

```env
# Set to your ACTUAL funded equity
# Guardian enforces 1% daily loss limit against this number
ZAR_FLOOR=2000.00
```

- [ ] 4.3 Ensure `MAX_ORDER_ZAR` is conservative:

```env
# Maximum single order — keep small for first trade
MAX_ORDER_ZAR=500
```

- [ ] 4.4 Save the file

---

## Section 5: Verify Balance via System

- [ ] 5.1 Ensure `.env` has `EXECUTION_MODE=LIVE_READ_ONLY` and `LIVE_READ_ONLY=TRUE`
- [ ] 5.2 Start the Docker stack:

```bash
cd /mnt/d/dev/repos/TRADE_BOT
docker compose -f docker-compose.local.yml up -d
```

- [ ] 5.3 Run the connectivity check:

```bash
python scripts/check_exchange_connectivity.py
```

- [ ] 5.4 Verify the balance check passes and shows your ZAR amount
- [ ] 5.5 Run the live readiness check:

```bash
python scripts/check_live_readiness.py
```

- [ ] 5.6 Confirm the balance section shows your funded amount

---

## Section 6: Verify Guardian Configuration

The Guardian uses `ZAR_FLOOR` to calculate the 1% daily loss limit.

- [ ] 6.1 Confirm `ZAR_FLOOR` matches your funded amount
- [ ] 6.2 Calculate your expected daily loss limit:

```
Daily loss limit = ZAR_FLOOR × 0.01
Example: R2,000 × 0.01 = R20 daily loss limit
```

- [ ] 6.3 Confirm this limit is acceptable (the system will lock after this much loss in a single day)
- [ ] 6.4 Verify Guardian is unlocked:

```bash
curl -s http://localhost:8080/guardian/status | python -m json.tool
```

Expected: `"locked": false`

---

## Section 7: Verify Kill Switch Readiness

- [ ] 7.1 Confirm `KILL_SWITCH_ENABLED=true` in `.env`
- [ ] 7.2 Verify you know how to trigger it:

```bash
# Emergency shutdown — cancels all pending orders and locks Guardian
python scripts/kill_switch.py
```

- [ ] 7.3 Verify you have the `GUARDIAN_ADMIN_TOKEN` and `GUARDIAN_RESET_CODE` stored securely (you will need these to unlock after a kill-switch or Guardian lockdown)

---

## Section 8: Pre-Trading Sanity Check

Before proceeding to the First Live Trade Checklist:

| Check | Expected | Your Result |
|---|---|---|
| VALR ZAR balance visible | Your funded amount | R_______ |
| `ZAR_FLOOR` in `.env` | Matches funded amount | _______ |
| `MAX_ORDER_ZAR` | ≤ R500 | _______ |
| `EXECUTION_MODE` | `LIVE_READ_ONLY` (not LIVE yet) | _______ |
| Guardian status | Unlocked | _______ |
| Kill switch accessible | Yes | _______ |
| `GUARDIAN_ADMIN_TOKEN` saved | Yes | _______ |
| `GUARDIAN_RESET_CODE` saved | Yes | _______ |

---

## Section 9: Common Deposit Issues

| Problem | Cause | Fix |
|---|---|---|
| Deposit not appearing after 3 days | Wrong reference used | Contact VALR support with proof of payment |
| Balance shows "Pending" | Deposit is processing | Wait for VALR to confirm (check email) |
| Balance shows R0 in system | `EXECUTION_MODE` is `DEMO` | Switch to `LIVE_READ_ONLY` to see real balances |
| Guardian locks immediately | `ZAR_FLOOR` too high | Set `ZAR_FLOOR` to your ACTUAL funded amount |
| Check script shows wrong amount | Stale data | Restart Docker containers, re-run script |

---

## Section 10: Next Steps

After completing this runbook:

1. **DO NOT** change `EXECUTION_MODE` to `LIVE` yet
2. Proceed to `DOCS/FIRST_LIVE_TRADE_CHECKLIST.md` for the go/no-go checklist
3. The First Live Trade Checklist will guide you through enabling `LIVE` mode safely

---

```
[Sovereign Reliability Audit]
- Classification: OPERATIONAL RUNBOOK (no code, no secrets)
- Sections: 10
- Risk Controls: MAX_ORDER_ZAR=500, ZAR_FLOOR=funded amount, Guardian 1%
- Deposit Guidance: Conservative (R1,000-R2,000 recommended)
- GitHub Data Sanitization: [Safe for Public — no account details]
- Traceability: [correlation_id: PHASE4-FUNDING-001]
```

---

*FUNDING_RUNBOOK.md v1.0.0 | Phase 4 | 2025-07-27 | SOVEREIGN TIER*

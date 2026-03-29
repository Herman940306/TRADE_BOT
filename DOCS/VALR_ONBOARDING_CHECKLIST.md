# VALR Onboarding Checklist — Autonomous Alpha

**Version:** 1.0.0
**Phase:** 4 — Operational Funding & First Live Trade Readiness
**Date:** 2025-07-27

---

## Purpose

Step-by-step guide for creating a VALR exchange account, generating API credentials, and verifying connectivity with the Autonomous Alpha system. This checklist assumes a beginner with no prior VALR experience.

> **Important:** VALR is a South African cryptocurrency exchange regulated by the FSCA. This checklist documents our integration. Exact UI labels and menu paths may change as VALR updates their platform. If a step does not match what you see, consult VALR's official documentation at [https://support.valr.com](https://support.valr.com).

---

## Step 1: Create a VALR Account

- [ ] 1.1 Navigate to [https://www.valr.com](https://www.valr.com)
- [ ] 1.2 Click **Sign Up** (or **Register**)
- [ ] 1.3 Enter your email address and create a strong, unique password
- [ ] 1.4 Verify your email address via the confirmation link VALR sends
- [ ] 1.5 Log in with your new credentials

---

## Step 2: Complete KYC Verification

VALR requires identity verification before you can deposit or trade.

- [ ] 2.1 Navigate to your **Profile** or **Settings** → **Verification** (or equivalent)
- [ ] 2.2 Submit the required identity documents (South African ID, passport, or equivalent)
- [ ] 2.3 Complete the selfie/liveness check if prompted
- [ ] 2.4 Wait for verification approval (may take minutes to days depending on queue)
- [ ] 2.5 Confirm your verification level permits **Trading** and **Deposits**

> **Note:** You do NOT need to complete advanced/institutional verification for initial testing. Basic individual verification is sufficient.

---

## Step 3: Enable Two-Factor Authentication (2FA)

- [ ] 3.1 Navigate to **Settings** → **Security** (or equivalent)
- [ ] 3.2 Enable 2FA using an authenticator app (Google Authenticator, Authy, etc.)
- [ ] 3.3 Save your 2FA backup/recovery codes in a secure location (password manager)
- [ ] 3.4 Verify 2FA works by logging out and logging back in

> **Critical:** 2FA is essential for protecting your API credentials. Do NOT skip this step.

---

## Step 4: Generate API Credentials

- [ ] 4.1 Navigate to **Settings** → **API Keys** (or equivalent section in VALR dashboard)
- [ ] 4.2 Click **Create API Key** (or equivalent button)
- [ ] 4.3 Set a descriptive label: `Autonomous Alpha - Live Trading`
- [ ] 4.4 Select the required permissions:

| Permission | Required | Purpose |
|---|---|---|
| **View** | YES | Read account balances, order history, market data |
| **Trade** | YES | Place and cancel limit orders |
| **Withdraw** | **NO — DO NOT ENABLE** | Not needed; protects against unauthorized withdrawals |

- [ ] 4.5 If VALR offers IP whitelisting for API keys, add the IP of your Docker host (optional but recommended)
- [ ] 4.6 Confirm creation (may require 2FA code)
- [ ] 4.7 **IMMEDIATELY** copy both values:
  - **API Key** → save securely
  - **API Secret** → save securely

> **WARNING:** The API Secret is shown ONLY ONCE at creation time. If you lose it, you must delete the key and create a new one. Store it in a password manager, not in plaintext files.

---

## Step 5: Store Credentials in `.env`

- [ ] 5.1 Open your `.env` file (NOT `.env.example` — your actual private `.env`)
- [ ] 5.2 Set the following values with your actual credentials:

```env
# VALR API Credentials — NEVER COMMIT THIS FILE
VALR_API_KEY=your_actual_api_key_here
VALR_API_SECRET=your_actual_api_secret_here
```

- [ ] 5.3 Verify `.env` is listed in `.gitignore` (it should be):

```bash
grep "\.env" .gitignore
# Expected output should include: .env
```

- [ ] 5.4 Confirm the `.env` file is NOT tracked by git:

```bash
git status .env
# Expected: file should NOT appear, or appear as "Untracked"
# If it appears as tracked — STOP and remove it from tracking immediately
```

---

## Step 6: Verify Connectivity (LIVE_READ_ONLY Mode)

Before enabling live trading, verify that your credentials work in read-only mode.

- [ ] 6.1 Set your `.env` to read-only mode:

```env
EXECUTION_MODE=LIVE_READ_ONLY
LIVE_READ_ONLY=TRUE
```

- [ ] 6.2 Run the connectivity check script from WSL:

```bash
cd /mnt/d/dev/repos/TRADE_BOT
python scripts/check_exchange_connectivity.py
```

- [ ] 6.3 Verify all 5 checks pass:

| Check | Expected Result |
|---|---|
| 1. VALR API Reachable | PASS |
| 2. Credentials Valid | PASS |
| 3. Market Data Available | PASS |
| 4. Account Balances Readable | PASS |
| 5. Trading Pair Available | PASS |

- [ ] 6.4 If any check fails, diagnose:
  - **Check 2 fails:** Invalid API key/secret — regenerate in Step 4
  - **Check 4 fails:** Insufficient permissions — verify "View" is enabled
  - **Check 5 fails:** Trading pair not found — verify pair format (e.g., `BTCZAR`)

---

## Step 7: Verify Mode Guard Safety

- [ ] 7.1 With `EXECUTION_MODE=LIVE_READ_ONLY`, confirm order placement is blocked:

```bash
python scripts/validate_live_path.py
```

- [ ] 7.2 Verify the script reports that order placement is correctly blocked in LIVE_READ_ONLY mode
- [ ] 7.3 Reset to PAPER mode when done testing:

```env
EXECUTION_MODE=DEMO
DEMO_MODE=PAPER
```

---

## Step 8: API Key Hygiene Checklist

- [ ] 8.1 Confirm **Withdraw** permission is NOT enabled on your API key
- [ ] 8.2 Confirm API key label identifies this application
- [ ] 8.3 Confirm `.env` is in `.gitignore`
- [ ] 8.4 Confirm no credentials appear in any committed file:

```bash
git log --all -p | grep -i "VALR_API" | head -5
# Expected: NO output (credentials never committed)
```

- [ ] 8.5 Confirm credentials are NOT in environment on the local machine (only in `.env` for Docker):

```bash
echo $VALR_API_KEY
# Expected: empty (not set in shell environment)
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `VALR-SEC-001: Missing VALR API credentials` | `VALR_API_KEY` or `VALR_API_SECRET` not in `.env` | Set both in `.env`, restart container |
| `ModeViolationError: MODE-003` | `LIVE_TRADING_CONFIRMED` not set for LIVE mode | This is expected in read-only — not needed yet |
| Connectivity check hangs | Network/firewall blocking `api.valr.com` | Check DNS, proxy, firewall rules |
| `401 Unauthorized` from VALR API | Invalid or expired API key | Regenerate API key in VALR dashboard |
| `403 Forbidden` on balances | "View" permission not granted | Re-create API key with correct permissions |

---

## System Integration Reference

Once credentials are verified in LIVE_READ_ONLY mode, the system uses them through this chain:

```
.env → os.getenv() → VALRSigner (HMAC-SHA512) → VALRClient → VALR REST API
```

| Component | File | Role |
|---|---|---|
| Credential loading | `app/exchange/hmac_signer.py` | Reads `VALR_API_KEY` + `VALR_API_SECRET` from env |
| Request signing | `app/exchange/hmac_signer.py` | Signs every request with HMAC-SHA512 |
| API client | `app/exchange/valr_client.py` | All REST calls: ticker, balances, orders |
| Mode enforcement | `app/exchange/mode_matrix.py` | Blocks orders unless LIVE_EXECUTION |
| Order placement | `app/exchange/order_manager.py` | Routes live orders through VALRClient |

---

```
[Sovereign Reliability Audit]
- Classification: ONBOARDING GUIDE (no code, no secrets)
- Steps: 8 sections, 30+ checkboxes
- Withdraw Permission: Explicitly blocked (Step 4.4)
- Credential Storage: .env only, gitignore verified
- GitHub Data Sanitization: [Safe for Public — no actual credentials]
- Traceability: [correlation_id: PHASE4-VALR-ONBOARD-001]
```

---

*VALR_ONBOARDING_CHECKLIST.md v1.0.0 | Phase 4 | 2025-07-27 | SOVEREIGN TIER*

# Production Environment Requirements — Autonomous Alpha

**Version:** 1.0.0
**Phase:** 4 — Operational Funding & First Live Trade Readiness
**Date:** 2025-07-27

---

## Purpose

This document is the single source of truth for every environment variable the system reads at runtime. Each variable is classified by the trading mode(s) that require it, its source, format, default value, and consequences if missing.

**Mode Key:**

| Abbreviation | Meaning |
|---|---|
| PAPER | Internal simulation — no exchange |
| DRY_RUN | Synthetic orders, public exchange data |
| LIVE_RO | Authenticated exchange reads, no orders |
| LIVE_EXEC | Real VALR order placement |

---

## 1. Database

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `DATABASE_URL` | All modes | *constructed* | `postgresql://user:pass@host:port/db` | `.env` | Falls back to `DB_*` vars |
| `DB_HOST` | All modes | `localhost` | hostname/IP | `.env` | Uses default |
| `DB_PORT` | All modes | `5432` | integer | `.env` | Uses default |
| `DB_NAME` | All modes | `autonomous_alpha` | string | `.env` | Uses default |
| `DB_USER` | All modes | `app_trading` | string | `.env` | Uses default |
| `DB_PASSWORD` | All modes | `trading_app_2024` | string | `.env` | **Insecure default — MUST override in production** |
| `DB_ECHO` | Optional | `false` | `true`/`false` | `.env` | `false` (SQL logging disabled) |
| `POSTGRES_PASSWORD` | All modes (Docker) | `sovereign_secret_2024` | string | `.env` → docker-compose | **Insecure default — MUST override in production** |
| `AURA_DB_PASSWORD` | Aura bridge only | `aura_readonly_2024` | string | `.env` | Aura MCP bridge cannot connect |
| `AURA_DATABASE_URL` | Aura bridge only | constructed | connection string | `.env` | Falls back to constructed URL |

### Critical Notes — Database

- **`DB_PASSWORD`** and **`POSTGRES_PASSWORD`** ship with hardcoded defaults. You MUST replace these with unique secrets before any funded operation.
- Generate with: `python -c "import secrets; print(secrets.token_hex(16))"`

---

## 2. Authentication & HMAC

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `SOVEREIGN_SECRET` | All modes | *None* | hex string, min 32 chars | `.env` | **Webhooks rejected — all signals fail** |
| `WEBHOOK_SECRET` | Email bridge | `""` | string | `.env` | Email bridge HMAC verification disabled |
| `GUARDIAN_ADMIN_TOKEN` | All modes | `""` | string | `.env` | Guardian API unlock endpoint disabled |
| `GUARDIAN_RESET_CODE` | All modes | `""` | string | `.env` | Cannot manually unlock Guardian after hard stop |
| `TRADINGVIEW_IP_WHITELIST` | All modes | TradingView IPs | comma-separated IPs/CIDRs | `.env` | Uses default TradingView IPs |
| `PREDICTION_HMAC_SECRET` | Internal | hardcoded | string | `.env` | Uses hardcoded default |
| `STRATEGY_FINGERPRINT_SECRET` | Internal | hardcoded | string | `.env` | Uses hardcoded default |

### Critical Notes — Authentication

- **`SOVEREIGN_SECRET`** is non-negotiable. Without it, no webhook signal can be verified.
- Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## 3. VALR Exchange

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `VALR_API_KEY` | LIVE_RO, LIVE_EXEC | `""` | alphanumeric | VALR dashboard | **Mode falls back to PAPER** |
| `VALR_API_SECRET` | LIVE_RO, LIVE_EXEC | `""` | alphanumeric | VALR dashboard | **Mode falls back to PAPER** |
| `VALR_RATE_LIMIT_CAPACITY` | Optional | `600` | integer | `.env` | 600 req/min default |
| `VALR_RATE_LIMIT_REFILL` | Optional | `10` | integer | `.env` | 10 tokens/sec default |

### Critical Notes — VALR

- VALR credentials are ONLY required for LIVE_READ_ONLY and LIVE_EXECUTION modes.
- Without valid credentials in LIVE mode, ModeGuard fails closed to PAPER.
- See `VALR_ONBOARDING_CHECKLIST.md` for credential creation steps.

---

## 4. Execution Mode & Trading Controls

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `EXECUTION_MODE` | All modes | `DEMO` | `DEMO` / `DRY_RUN` / `LIVE` / `LIVE_READ_ONLY` | `.env` | Defaults to `DEMO` (PAPER) |
| `DEMO_MODE` | PAPER only | `PAPER` | `PAPER` / `OANDA_PRACTICE` / `BINANCE_TESTNET` | `.env` | Defaults to `PAPER` |
| `DEMO_STATE_FILE` | PAPER only | `data/demo_broker_state.json` | file path | `.env` | Uses default path |
| `LIVE_TRADING_CONFIRMED` | LIVE_EXEC only | `""` | Must be exactly `TRUE` | `.env` | **LIVE mode blocked — falls back to PAPER** |
| `LIVE_READ_ONLY` | LIVE_RO only | `""` | `TRUE` to enable | `.env` | LIVE_READ_ONLY not activated |
| `MAX_ORDER_ZAR` | LIVE_EXEC | `5000` | integer (ZAR) | `.env` | R5,000 default cap |
| `STRATEGY_MODE` | All modes | `DETERMINISTIC` | `DETERMINISTIC` / `STOCHASTIC` | `.env` | Defaults to `DETERMINISTIC` |

### Critical Notes — Execution Mode

- **`LIVE_TRADING_CONFIRMED`** is the final safety gate. It must be the string `TRUE` (case-insensitive). Any other value, including `true`, `yes`, or `1`, causes ModeGuard to fall back to PAPER.
- **`MAX_ORDER_ZAR`** is the hard cap per single order. R500 recommended for first live trade.

---

## 5. Guardian Service

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `ZAR_FLOOR` | All modes | `100000.00` | decimal string (ZAR) | `.env` | Uses R100,000 default |
| `GUARDIAN_LOCK_FILE` | All modes | `data/guardian_lock.json` | file path | `.env` | Uses default path |
| `GUARDIAN_AUDIT_DIR` | All modes | `data/guardian_audit` | directory path | `.env` | Uses default path |
| `KILL_SWITCH_ENABLED` | All modes | `true` | `true`/`false` | `.env` | Kill switch enabled by default |

### Critical Notes — Guardian

- **`ZAR_FLOOR`** must reflect your actual funded equity for the 1% daily loss limit to work correctly.
- For a first live trade with R2,000 funding, set `ZAR_FLOOR=2000.00`.

---

## 6. HITL (Human-In-The-Loop)

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `HITL_ENABLED` | All modes | `true` | `true`/`false` | `.env` | HITL gate enabled by default |
| `HITL_TIMEOUT_SECONDS` | All modes | `300` | integer (seconds) | `.env` | 5-minute timeout |
| `HITL_SLIPPAGE_MAX_PERCENT` | All modes | `0.5` | decimal (percent) | `.env` | 0.5% max slippage |
| `HITL_ALLOWED_OPERATORS` | All modes | `""` | comma-separated operator IDs | `.env` | **No operator can approve trades** |
| `HITL_EXPIRY_INTERVAL_SECONDS` | All modes | `30` | integer (seconds) | `.env` | 30-second check interval |

### Critical Notes — HITL

- **`HITL_ALLOWED_OPERATORS`** must contain at least one operator ID (e.g., `operator_alpha`). Without this, no human can approve any trade.

---

## 7. Discord Notifications

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `DISCORD_WEBHOOK_URL` | Optional | *None* | `https://discord.com/api/webhooks/...` | Discord server settings | Notifications silently disabled |
| `DISCORD_ALERT_LEVEL` | Optional | `WARNING` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` | `.env` | Only WARNING+ sent |
| `DISCORD_RATE_LIMIT_SECONDS` | Optional | `5` | integer (seconds) | `.env` | 5-second rate limit |
| `DISCORD_NOTIFICATIONS_ENABLED` | Optional | auto | `true`/`false` | `.env` | Enabled if URL is set |

---

## 8. AI / LLM (Cold Path)

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `OPENROUTER_API_KEY` | All modes (AI consensus) | *None* | string | OpenRouter dashboard | **AI Council consensus disabled — trades may still proceed via fallback** |
| `USE_LOCAL_OLLAMA` | Optional | `""` (false) | `true`/`false` | `.env` | Uses OpenRouter |
| `OLLAMA_BASE_URL` | Ollama only | `http://ollama:11434` | URL | `.env` | Default endpoint |
| `OLLAMA_MODEL` | Ollama only | `deepseek-r1:7b` | model name | `.env` | Default model |
| `AI_CONSENSUS_THRESHOLD` | All modes | `60` | integer (0-100) | `.env` | 60% threshold |

---

## 9. Data Ingestion (Multi-Source)

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `BINANCE_API_KEY` | Optional | `""` | string | Binance dashboard | Binance adapter disabled |
| `BINANCE_API_SECRET` | Optional | `""` | string | Binance dashboard | Binance adapter disabled |
| `OANDA_API_KEY` | Optional | `""` | string | OANDA dashboard | OANDA adapter disabled |
| `OANDA_ACCOUNT_ID` | Optional | `""` | string | OANDA dashboard | OANDA adapter disabled |
| `TWELVE_DATA_API_KEY` | Optional | `""` | string | Twelve Data dashboard | Twelve Data adapter disabled |

---

## 10. Risk Management

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `TEST_EQUITY` | PAPER, DRY_RUN | `100000` | integer (ZAR) | `.env` | R100,000 test equity |
| `MAX_RISK_ZAR` | All modes | `5000` | integer (ZAR) | `.env` | R5,000 max risk per trade |

---

## 11. RGI (Reward-Governed Intelligence)

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `RGI_MODEL_PATH` | Optional | `models/reward_governor.txt` | file path | `.env` | Uses default path |
| `RGI_RUN_GOLDEN_SET` | Optional | `true` | `true`/`false` | `.env` | Golden set runs on startup |

---

## 12. Sovereign Gateway (NAS SSH)

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `GATEWAY_IP` | NAS bridge only | `127.0.0.1` | IP address | `.env` | Uses localhost |
| `GATEWAY_USER` | NAS bridge only | `admin` | string | `.env` | Uses admin |
| `SOVEREIGN_GATEWAY_PASSWORD` | NAS bridge only | *None* | string | `.env` | **Bridge cannot connect to NAS** |

---

## 13. Email Bridge

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `EMAIL_USER` | Email bridge only | *None* | Gmail address | `.env` | Bridge cannot poll email |
| `EMAIL_PASS` | Email bridge only | *None* | Gmail App Password | `.env` | Bridge cannot poll email |
| `IMAP_SERVER` | Email bridge only | `imap.gmail.com` | hostname | `.env` | Uses default |
| `IMAP_PORT` | Email bridge only | `993` | integer | `.env` | Uses default |
| `BOT_URL` | Email bridge only | `http://bot:8080/webhook/tradingview` | URL | `.env` | Uses default |
| `POLL_INTERVAL` | Email bridge only | `10` | integer (seconds) | `.env` | 10-second polling |
| `TRADINGVIEW_SENDER` | Email bridge only | `noreply@tradingview.com` | email address | `.env` | Uses default |

---

## 14. Infrastructure

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `AURA_BRIDGE_URL` | Aura client | `http://aura_bridge:8086` | URL | `.env` | Uses default |
| `AURA_PORT` | Aura bridge | `8086` | integer | `.env` | Uses default |
| `PROMETHEUS_URL` | Aura bridge | `http://prometheus:9090` | URL | `.env` | Uses default |
| `CORS_ORIGINS` | All modes | `*` | comma-separated origins | `.env` | **Wildcard — restrict in production** |
| `GRAFANA_ADMIN_PASSWORD` | Grafana | `sovereign_grafana_2024` | string | `.env` | **Insecure default** |

---

## 15. Reconciliation & Market Data

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `RECONCILIATION_INTERVAL_SECONDS` | LIVE_RO, LIVE_EXEC | `60` | integer (seconds) | `.env` | 60-second interval |
| `RECONCILIATION_MISMATCH_THRESHOLD_PCT` | LIVE_RO, LIVE_EXEC | `1.0` | decimal (percent) | `.env` | 1% threshold |
| `RECONCILIATION_MAX_FAILURES` | LIVE_RO, LIVE_EXEC | `3` | integer | `.env` | 3 failures before neutral |
| `MARKET_DATA_POLL_INTERVAL` | DRY_RUN, LIVE_RO, LIVE_EXEC | `5` | integer (seconds) | `.env` | 5-second polling |
| `MARKET_DATA_STALENESS_THRESHOLD` | DRY_RUN, LIVE_RO, LIVE_EXEC | `30` | integer (seconds) | `.env` | 30-second threshold |
| `MARKET_DATA_UNREACHABLE_THRESHOLD` | DRY_RUN, LIVE_RO, LIVE_EXEC | `60` | integer (seconds) | `.env` | 60-second threshold |
| `MARKET_DATA_MAX_SPREAD_PCT` | DRY_RUN, LIVE_RO, LIVE_EXEC | `2.0` | decimal (percent) | `.env` | 2% max spread |

---

## 16. Python Runtime (Docker)

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `PYTHONUNBUFFERED` | Docker | `1` | `1` | docker-compose | Set automatically |
| `PYTHONDONTWRITEBYTECODE` | Docker | `1` | `1` | docker-compose | Set automatically |
| `ENV` | Optional | `""` | `production`/`development` | `.env` | Discord shows "Development" |

---

## 17. Policy & Budget

| Variable | Required In | Default | Format | Source | If Missing |
|---|---|---|---|---|---|
| `TRADE_POLICY_LAYER_ENABLED` | All modes | `true` | `true`/`false` | `.env` | Policy layer enabled |
| `BUDGETGUARD_JSON_PATH` | Optional | `budget_report.json` | file path | `.env` | Uses default path |
| `BUDGETGUARD_STRICT_MODE` | Optional | `false` | `true`/`false` | `.env` | Non-strict (allows trading without budget) |

---

## Summary: Variables Required for First Live Trade

To go from PAPER to LIVE_EXECUTION with a funded VALR account, the operator MUST set these variables beyond defaults:

| # | Variable | Why |
|---|---|---|
| 1 | `EXECUTION_MODE=LIVE` | Selects live execution path |
| 2 | `LIVE_TRADING_CONFIRMED=TRUE` | Explicit confirmation gate |
| 3 | `VALR_API_KEY=<your key>` | VALR API authentication |
| 4 | `VALR_API_SECRET=<your secret>` | VALR API authentication |
| 5 | `SOVEREIGN_SECRET=<64+ hex chars>` | Webhook HMAC verification |
| 6 | `HITL_ALLOWED_OPERATORS=<operator_id>` | At least one human approver |
| 7 | `DB_PASSWORD=<unique secret>` | Override insecure default |
| 8 | `POSTGRES_PASSWORD=<unique secret>` | Override insecure default |
| 9 | `ZAR_FLOOR=<funded equity>` | Accurate Guardian 1% limit |
| 10 | `MAX_ORDER_ZAR=500` | Conservative first-trade cap |
| 11 | `GUARDIAN_ADMIN_TOKEN=<token>` | Ability to unlock Guardian |
| 12 | `GUARDIAN_RESET_CODE=<code>` | Ability to reset after hard stop |

---

```
[Sovereign Reliability Audit]
- Classification: ENV SPECIFICATION (no code, no secrets)
- Variables Catalogued: 70+
- Production Hardcoded Defaults Flagged: DB_PASSWORD, POSTGRES_PASSWORD, GRAFANA_ADMIN_PASSWORD, CORS_ORIGINS
- GitHub Data Sanitization: [Safe for Public — no actual values]
- Traceability: [correlation_id: PHASE4-ENV-SPEC-001]
```

---

*PRODUCTION_ENV_REQUIREMENTS.md v1.0.0 | Phase 4 | 2025-07-27 | SOVEREIGN TIER*

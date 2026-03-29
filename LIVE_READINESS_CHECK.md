# Live Readiness Check — Phase 3A

**Version:** 1.0.0
**Date:** 2026-03-29
**Reliability Level:** SOVEREIGN TIER

---

## 1. Purpose

This document defines the prerequisites, diagnostics, and acceptance criteria required before progressing from paper trading (Phase 2B) to live exchange connectivity (Phase 3A and beyond). It accompanies the automated diagnostics scripts.

---

## 2. Automated Diagnostics

### 2.1 Exchange Connectivity

```bash
python3 scripts/check_exchange_connectivity.py
```

| Check | Auth Required | Expected |
|-------|--------------|----------|
| Public API (BTCZAR ticker) | No | JSON with bid/ask/last |
| Server time / clock drift | No | Drift < 1000ms |
| API credentials configured | N/A | `VALR_API_KEY` and `VALR_API_SECRET` set |
| Authenticated balance read | Yes | ZAR balance returned |
| Open orders query | Yes | List (may be empty) |

### 2.2 Live Readiness (Full Pre-Flight)

```bash
python3 scripts/check_live_readiness.py
```

| Category | Critical Checks |
|----------|----------------|
| Mode Matrix | ModeGuard initializes, LIVE_EXECUTION disabled, order placement blocked |
| Exchange | Public API, credentials, authenticated read |
| Equity | EquitySource initializes, retrieval returns value |
| Guardian | Service importable, system not locked |
| HITL | Gateway importable, operators configured |
| Reconciliation | Engine importable, threshold configured |
| Database | DATABASE_URL configured |

---

## 3. Mode Matrix

| Mode | Public Data | Auth Reads | Orders | Equity Source | Credentials Required |
|------|-------------|-----------|--------|---------------|---------------------|
| PAPER | No | No | No | DemoBroker | No |
| DRY_RUN | Yes | No | No | Static (ZAR_FLOOR) | No |
| LIVE_READ_ONLY | Yes | Yes | No | VALR Exchange | Yes |
| LIVE_EXECUTION | Yes | Yes | Yes | VALR Exchange | Yes |

### 3.1 Mode Resolution

The `ModeGuard` resolves mode from environment variables:

| Env Var | Value | Resulting Mode |
|---------|-------|----------------|
| `EXECUTION_MODE=DEMO` | `DEMO_MODE=PAPER` | `PAPER` |
| `EXECUTION_MODE=DRY_RUN` | — | `DRY_RUN` |
| `EXECUTION_MODE=LIVE_READ_ONLY` | — | `LIVE_READ_ONLY` |
| `LIVE_READ_ONLY=TRUE` | — | `LIVE_READ_ONLY` |
| `EXECUTION_MODE=LIVE` | `LIVE_TRADING_CONFIRMED=TRUE` | `LIVE_EXECUTION` |
| `EXECUTION_MODE=LIVE` | (no confirmation) | `PAPER` (fail-closed) |
| Unknown | — | `PAPER` (fail-closed) |

### 3.2 Hard Guards

Every operation that touches the exchange checks the mode guard:

- `require_public_data()` — blocks in PAPER mode
- `require_authenticated_read()` — blocks in PAPER and DRY_RUN modes
- `require_order_placement()` — blocks in all modes except LIVE_EXECUTION

---

## 4. Equity Source

| Mode | Source | Implementation |
|------|--------|---------------|
| PAPER | DemoBroker | `DemoBroker.get_account_equity()` |
| DRY_RUN | Static | `ZAR_FLOOR` env var (default: R100,000) |
| LIVE_READ_ONLY | VALR Exchange | `VALRClient.get_balances()` → ZAR total |
| LIVE_EXECUTION | VALR Exchange | `VALRClient.get_balances()` → ZAR total |

### 4.1 Fail-Closed Behavior

If the equity source fails to return a value (`None`), the caller must:
1. Block all new trades
2. Log the failure with error code `EQUITY-001/002/003`
3. Notify via Discord (if configured)

The `EquitySource` never fabricates a value. It returns `None` on failure.

---

## 5. Reconciliation

### 5.1 3-Way Sync

The `ReconciliationEngine` compares:

| Source | Description | Implementation |
|--------|-------------|---------------|
| Exchange | VALR account balance | `VALRClient.get_balances()` |
| Database | Net position from filled orders | `SELECT SUM(CASE...) FROM trading_orders` |
| State | In-memory tracking | `ReconciliationEngine._state_balances` |

### 5.2 Thresholds

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Balance mismatch | > 1% | L6 Lockdown (Guardian lock) |
| Consecutive failures | >= 3 | Neutral State (full stop) |
| Reconciliation interval | 60 seconds | Periodic check |

### 5.3 Database Query

The real reconciliation query (replaces the former placeholder):

```sql
SELECT COALESCE(
  SUM(CASE WHEN side = 'BUY' THEN filled_quantity
           WHEN side = 'SELL' THEN -filled_quantity
           ELSE 0 END), 0
) AS net_balance
FROM trading_orders
WHERE base_currency = :currency
AND status = 'FILLED'
```

---

## 6. Phase 3A Transition Checklist

### 6.1 Before Enabling LIVE_READ_ONLY

- [ ] VALR API key created with **View** permissions only (no Trade)
- [ ] `VALR_API_KEY` and `VALR_API_SECRET` set in `.env`
- [ ] `EXECUTION_MODE=LIVE_READ_ONLY` in `.env`
- [ ] `scripts/check_exchange_connectivity.py` passes all checks
- [ ] `scripts/check_live_readiness.py` passes all critical checks
- [ ] Guardian is UNLOCKED
- [ ] Docker stack boots cleanly (`docker compose up`)

### 6.2 Before Enabling LIVE_EXECUTION

- [ ] All Phase 3A checks pass
- [ ] VALR API key upgraded to **Trade** permissions
- [ ] `EXECUTION_MODE=LIVE` and `LIVE_TRADING_CONFIRMED=TRUE` in `.env`
- [ ] Risk limits reviewed: `MAX_ORDER_ZAR`, `ZAR_FLOOR`
- [ ] Reconciliation running without mismatches for >= 24 hours
- [ ] Human operator available for HITL approvals
- [ ] Kill switch tested and verified

---

## 7. Emergency Procedures

### 7.1 Kill Switch

```bash
python3 scripts/kill_switch.py
```

### 7.2 Guardian Lock

Lock the system via API:
```bash
curl -X POST http://localhost:8080/api/v1/guardian/lock \
  -H "Authorization: Bearer $GUARDIAN_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual emergency lock", "correlation_id": "EMERGENCY-001"}'
```

### 7.3 Mode Downgrade

Change `.env` and restart:
```bash
# Downgrade to PAPER mode
EXECUTION_MODE=DEMO
DEMO_MODE=PAPER
```

---

*LIVE_READINESS_CHECK.md v1.0.0 | Phase 3A | SOVEREIGN TIER*

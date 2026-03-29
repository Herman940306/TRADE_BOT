# Live Execution Runbook — Project Autonomous Alpha

**Version:** 1.0.0
**Phase:** 3B — Controlled Live Order Placement
**Reliability Level:** SOVEREIGN TIER
**Last Updated:** 2025-01-26

---

## 1. Architecture Overview

The live execution pipeline is a layered, fail-closed system where every order must pass through multiple independent safety gates before reaching the exchange.

```
Trade Lifecycle (ACCEPTED state, post-HITL approval)
  │
  ├── LiveExecutionBridge._preflight()
  │     ├── ModeGuard.can_place_orders()          [TradingMode == LIVE_EXECUTION]
  │     ├── Guardian._system_locked == False       [Not in lockdown]
  │     ├── Duplicate trade check                  [trade_id not in _executed_trade_ids]
  │     ├── RolloutLimits.max_order_zar            [R500 default]
  │     ├── RolloutLimits.max_daily_trades         [5 default]
  │     ├── RolloutLimits.max_daily_zar_volume     [R2,500 default]
  │     ├── RolloutLimits.max_per_symbol_trades    [3 default]
  │     ├── EquitySource.get_equity_zar() != None  [Live equity available]
  │     └── ReconciliationEngine is configured     [Recon engine present]
  │
  ├── OrderManager._execute_live_order()
  │     ├── VALRClient exists
  │     ├── VALRClient.is_authenticated()
  │     ├── Generate AA_{uuid} client order ID
  │     └── VALRClient.place_limit_order()  →  POST /v1/orders/limit
  │           └── post_only=True (maker-only, prevents taking)
  │
  ├── OrderStatusPoller.track_order()
  │     ├── poll_once() → GET /v1/orders/{pair}/orderid/{id}
  │     ├── State transitions: NEW → PLACED → PARTIALLY_FILLED → FILLED
  │     ├── Terminal states: FILLED, CANCELLED, FAILED, EXPIRED
  │     ├── Stale detection: >3600s → FAILED
  │     └── Callbacks: on_fill, on_partial_fill, on_cancel, on_fail
  │
  └── LiveExecutionBridge.reconcile_after_fill()
        ├── Update state balance (BUY → add, SELL → subtract)
        ├── ReconciliationEngine.reconcile()
        └── Mismatch >1% → Guardian lockdown
```

## 2. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `EXECUTION_MODE` | Yes | `DRY_RUN` | Must be `LIVE` for live orders |
| `LIVE_TRADING_CONFIRMED` | Yes | _(none)_ | Must be `TRUE` (case-insensitive) |
| `VALR_API_KEY` | Yes | _(none)_ | VALR API key with trade permissions |
| `VALR_API_SECRET` | Yes | _(none)_ | VALR API secret (HMAC-SHA512) |
| `MAX_ORDER_ZAR` | No | `5000` | Maximum single order value in ZAR |
| `DATABASE_URL` | Yes | _(none)_ | PostgreSQL connection string |

### Mode Resolution

| EXECUTION_MODE | LIVE_TRADING_CONFIRMED | Result |
|---|---|---|
| `DRY_RUN` / unset | Any | `PAPER` mode — no exchange calls |
| `LIVE` | `TRUE` | `LIVE_EXECUTION` — real orders enabled |
| `LIVE` | Anything else | Falls back to `PAPER` |
| `LIVE_READ_ONLY` | Any | Read-only — ticker/balance queries only |

## 3. Safety Gates (Fail-Closed)

### Gate 1: ModeGuard (mode_matrix.py)
- Resolves `EXECUTION_MODE` → `TradingMode` enum
- `LIVE_EXECUTION` requires **both** `EXECUTION_MODE=LIVE` **and** `LIVE_TRADING_CONFIRMED=TRUE`
- `require_live_execution_prerequisites()` validates: mode, confirmation, API key, API secret
- Any missing → `ModeViolationError` raised, no fallback

### Gate 2: Order Manager Auth Check (order_manager.py)
- `_execute_live_order()` verifies VALRClient exists (`VALR-ORD-003`)
- `_execute_live_order()` verifies `client.is_authenticated()` (`VALR-ORD-005`)
- MARKET orders globally rejected (`VALR-ORD-001`) — LIMIT only
- `MAX_ORDER_ZAR` enforced on all orders (`VALR-ORD-002`)

### Gate 3: LiveExecutionBridge Preflight (live_execution_bridge.py)
- 9-point pre-flight before any order reaches the exchange
- Guardian lock check → `BRIDGE-004`
- Duplicate trade_id detection → `BRIDGE-006`
- Rollout limits (order value, daily trades, daily volume, per-symbol) → `BRIDGE-001`
- Equity check → `BRIDGE-005`
- Reconciliation engine required → `BRIDGE-001`

### Gate 4: VALR API (valr_client.py)
- `post_only=True` forces maker-only orders (prevents market-taking)
- HMAC-SHA512 signature on every authenticated request
- Rate limiting via TokenBucket (600 requests/minute)
- Exponential backoff on HTTP 429

## 4. Error Codes

| Code | Module | Description |
|---|---|---|
| `MODE-002` | ModeGuard | Order placement blocked in current mode |
| `MODE-003` | ModeGuard | Live execution prerequisites not met |
| `VALR-ORD-001` | OrderManager | MARKET order rejected (LIMIT only) |
| `VALR-ORD-002` | OrderManager | Order exceeds MAX_ORDER_ZAR |
| `VALR-ORD-003` | OrderManager | No VALRClient for LIVE order |
| `VALR-ORD-004` | OrderManager | Unexpected live order failure |
| `VALR-ORD-005` | OrderManager | Missing VALR credentials |
| `VALR-ORD-006` | OrderManager | Insufficient exchange balance |
| `VALR-ORD-007` | OrderManager | Invalid trading pair / precision |
| `VALR-ORD-008` | OrderManager | Rate limit exceeded |
| `VALR-ORD-009` | OrderManager | Exchange unavailable (5xx/connection) |
| `VALR-ORD-010` | OrderManager | Request timeout |
| `VALR-POLL-001` | Poller | Polling cycle failed (transient) |
| `VALR-POLL-002` | Poller | Order stale (exceeded max poll age) |
| `VALR-POLL-003` | Poller | Unknown VALR orderStatusType |
| `BRIDGE-001` | Bridge | Pre-flight check failed |
| `BRIDGE-002` | Bridge | Order placement failed |
| `BRIDGE-003` | Bridge | Post-fill reconciliation mismatch |
| `BRIDGE-004` | Bridge | Guardian locked |
| `BRIDGE-005` | Bridge | Equity unavailable |
| `BRIDGE-006` | Bridge | Duplicate execution attempt |

## 5. Rollout Limits

Default rollout limits for initial live trading:

| Limit | Default | Description |
|---|---|---|
| `max_order_zar` | R500 | Maximum single order value |
| `max_daily_trades` | 5 | Maximum trades per day |
| `max_daily_zar_volume` | R2,500 | Maximum daily ZAR exposure |
| `max_per_symbol_trades` | 3 | Maximum trades per trading pair |

These are enforced by `LiveExecutionBridge._preflight()` **in addition to** the OrderManager's `MAX_ORDER_ZAR` limit.

To override, pass a custom `RolloutLimits` dataclass:
```python
from app.exchange.live_execution_bridge import RolloutLimits
limits = RolloutLimits(
    max_order_zar=Decimal("1000"),
    max_daily_trades=10,
)
```

## 6. Order Lifecycle

```
State Machine:
  SUBMITTED → PLACED → PARTIALLY_FILLED → FILLED (terminal)
                     → CANCELLED (terminal)
                     → FAILED (terminal)
                     → EXPIRED (terminal)
```

### VALR Status Mapping

| VALR orderStatusType | Internal State | Terminal? |
|---|---|---|
| Active | NEW | No |
| Placed | PLACED | No |
| Partially Filled | PARTIALLY_FILLED | No |
| Filled | FILLED | Yes |
| Instant Order Completed | FILLED | Yes |
| Cancelled | CANCELLED | Yes |
| Failed | FAILED | Yes |
| Expired | EXPIRED | Yes |
| _(unknown)_ | FAILED | Yes |

## 7. First Live Trade Checklist

Before placing the first real order:

- [ ] `.env` has `EXECUTION_MODE=LIVE`
- [ ] `.env` has `LIVE_TRADING_CONFIRMED=TRUE`
- [ ] `.env` has valid `VALR_API_KEY` with trade permissions
- [ ] `.env` has valid `VALR_API_SECRET`
- [ ] `.env` has `DATABASE_URL` pointing to production database
- [ ] VALR account has sufficient ZAR balance
- [ ] Guardian is not locked (`_system_locked == False`)
- [ ] `scripts/check_exchange_connectivity.py` passes
- [ ] `scripts/check_live_readiness.py` passes
- [ ] `scripts/validate_live_path.py` passes (32/32 dry checks)
- [ ] `python -m pytest tests/unit/test_live_execution.py` passes (59/59)
- [ ] `python -m pytest tests/unit/test_mode_matrix_equity.py` passes (32/32)
- [ ] Docker containers are running (`docker compose up -d`)
- [ ] Monitoring/alerting configured (Grafana dashboards)
- [ ] HITL approval flow functional (Discord/webhook)

### Kill Switch

```bash
# Emergency: Immediately disable all live trading
python scripts/kill_switch.py
```

This sets Guardian to locked state and prevents all further order placement.

## 8. Monitoring & Diagnostics

### Bridge Status
```python
bridge.get_status()
# Returns:
# {
#   "mode": "LIVE_EXECUTION",
#   "executed_trades": 1,
#   "daily_trades": 1,
#   "daily_zar_volume": "150.00",
#   "symbol_counts": {"BTCZAR": 1},
#   "rollout_limits": {...},
#   "poller_active": 0,
#   "correlation_id": "..."
# }
```

### Poller Status
```python
poller.get_status()
# Returns:
# {
#   "tracked_total": 5,
#   "active": 1,
#   "terminal": 4,
#   "transitions_recorded": 8,
#   "correlation_id": "..."
# }
```

### ModeGuard Status
```python
guard.get_status()
# Returns current mode, capabilities, env vars
```

### Log Markers

All live-path operations are logged with structured markers:

| Marker | Description |
|---|---|
| `[LIVE]` | Live order placement/result |
| `[BRIDGE]` | LiveExecutionBridge operations |
| `[VALR-POLL]` | Order status polling |
| `[MODE]` | Mode guard operations |
| `[VALR-ORD-xxx]` | Order manager errors |
| `[BRIDGE-xxx]` | Bridge errors |

Every log entry includes `correlation_id` for end-to-end tracing.

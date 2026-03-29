# Post-Trade Review Checklist — Autonomous Alpha

**Version:** 1.0.0
**Phase:** 4 — Operational Funding & First Live Trade Readiness
**Date:** 2025-07-27

---

## Purpose

Verification checklist to execute immediately after your first live trade completes (or fails). This ensures the system behaved correctly, the order is properly recorded, and no anomalies occurred.

> **Mandate:** Every trade, whether successful or not, must leave a complete audit trail.

---

## When to Use This Checklist

Use this checklist after:
- A live order was submitted (whether filled, partially filled, or rejected)
- A HITL approval was granted and the execution path ran
- Any unexpected behavior during a live trading session

---

## Section 1: Order Acceptance Verification

| # | Check | How to Verify | Result |
|---|---|---|---|
| 1.1 | Order was submitted to VALR | Check application logs for `VALR-ORD-*` entries | [ ] Pass / [ ] Fail |
| 1.2 | VALR returned an order ID | Logs show `order_id=<uuid>` | [ ] Pass / [ ] Fail |
| 1.3 | Order appears on VALR dashboard | Log in → Open Orders or Order History | [ ] Pass / [ ] Fail |
| 1.4 | Order was `post_only=True` (maker) | Logs show `post_only=True` in placement data | [ ] Pass / [ ] Fail |

**If 1.1 fails:** The order was blocked before reaching VALR — check preflight errors in logs.
**If 1.2 fails:** VALR rejected the order — check error code (VALR-ORD-003 through VALR-ORD-010).

---

## Section 2: Fill Status

| # | Check | How to Verify | Result |
|---|---|---|---|
| 2.1 | Order status is terminal | One of: FILLED, PARTIALLY_FILLED, CANCELLED, EXPIRED, FAILED | [ ] |
| 2.2 | Fill price is at or better than limit | Compare fill price to your limit price | [ ] |
| 2.3 | Fill quantity matches order quantity | VALR dashboard → Order History → compare | [ ] |
| 2.4 | No unexpected duplicate orders | VALR dashboard shows exactly 1 order (not 2+) | [ ] |

**Record the fill details:**

| Field | Value |
|---|---|
| Order ID | |
| Trading pair | |
| Side (BUY/SELL) | |
| Limit price | |
| Fill price | |
| Quantity | |
| ZAR value | |
| Status | |

---

## Section 3: Database State

| # | Check | How to Verify | Result |
|---|---|---|---|
| 3.1 | Trade recorded in `trade_lifecycle` table | Query DB or check logs for lifecycle state | [ ] |
| 3.2 | State transitions recorded | `trade_state_transitions` table has entries | [ ] |
| 3.3 | Final state matches VALR status | DB state = VALR terminal state | [ ] |
| 3.4 | No orphaned records | No trades stuck in ACCEPTED without progression | [ ] |

**Database query (from inside Docker container):**

```bash
docker compose -f docker-compose.local.yml exec db \
  psql -U app_trading -d autonomous_alpha -c \
  "SELECT id, state, symbol, side, created_at FROM trade_lifecycle ORDER BY created_at DESC LIMIT 5;"
```

---

## Section 4: Reconciliation

| # | Check | How to Verify | Result |
|---|---|---|---|
| 4.1 | VALR ZAR balance changed correctly | VALR dashboard → Wallets → ZAR | [ ] |
| 4.2 | Crypto balance changed correctly | VALR dashboard → Wallets → BTC (or relevant) | [ ] |
| 4.3 | Balance delta matches trade value | Deposit - current ZAR ≈ trade ZAR value + fees | [ ] |
| 4.4 | No reconciliation mismatch in logs | `grep "RECON" docker logs` — no MISMATCH entries | [ ] |

**Record the balance delta:**

| Field | Before Trade | After Trade | Delta |
|---|---|---|---|
| ZAR Available | | | |
| Crypto Available | | | |
| Fees paid (ZAR) | N/A | | |

---

## Section 5: Audit Trail

| # | Check | How to Verify | Result |
|---|---|---|---|
| 5.1 | HITL approval was recorded | DB has approval record with operator ID and timestamp | [ ] |
| 5.2 | `correlation_id` traces end-to-end | Single correlation_id from signal → approval → execution | [ ] |
| 5.3 | Guardian daily P&L updated | `curl -s http://localhost:8080/guardian/status` shows updated P&L | [ ] |
| 5.4 | Discord notification sent (if configured) | Check Discord channel for trade notification | [ ] |

---

## Section 6: Safety System Verification

| # | Check | How to Verify | Result |
|---|---|---|---|
| 6.1 | Guardian is still unlocked | Guardian status → `locked: false` | [ ] |
| 6.2 | Daily trade count incremented | Rollout guard shows 1 trade used | [ ] |
| 6.3 | Rollout limits not exceeded | ≤ 5 trades/day, ≤ R2,500/day, ≤ 3/symbol | [ ] |
| 6.4 | No unexpected error codes in logs | `grep "ERROR\|CRITICAL" logs` — review each | [ ] |

---

## Section 7: Anomaly Detection

| # | Check | Expected | Result |
|---|---|---|---|
| 7.1 | Only ONE order was placed | Exactly 1 in VALR order history for this session | [ ] |
| 7.2 | No orders were placed for wrong pairs | All orders are for your intended pair | [ ] |
| 7.3 | No BUY when you expected SELL (or vice versa) | Side matches signal direction | [ ] |
| 7.4 | OrderStatusPoller stopped cleanly | No active polling loops after terminal state | [ ] |
| 7.5 | System returned to ready state | Health endpoint shows `operational` | [ ] |

**If ANY anomaly is detected:**
1. Immediately set `EXECUTION_MODE=DEMO` in `.env`
2. Restart the stack
3. Investigate the anomaly before re-enabling live mode

---

## Section 8: Post-Review Actions

### If everything passed:

- [ ] Record this trade in your personal trade journal (date, pair, size, result)
- [ ] Consider keeping `EXECUTION_MODE=LIVE` for the next signal
- [ ] Monitor for the next 24 hours for any delayed anomalies

### If any check failed:

- [ ] Set `EXECUTION_MODE=DEMO` immediately
- [ ] Document the failure with timestamps and log excerpts
- [ ] Do NOT re-enable live mode until the root cause is understood
- [ ] If a code fix is needed, it must go through the full test suite before re-deployment

### After your first successful trade:

- [ ] Congratulations — the system has completed its first real-money cycle
- [ ] Consider gradually increasing `MAX_ORDER_ZAR` (no more than doubling at a time)
- [ ] Keep `ZAR_FLOOR` accurate as your funded equity changes

---

```
[Sovereign Reliability Audit]
- Classification: POST-TRADE REVIEW (no code, no secrets)
- Sections: 8
- Verification checks: 27
- Covers: Order acceptance, fills, DB state, recon, audit trail, anomalies
- GitHub Data Sanitization: [Safe for Public — no account data]
- Traceability: [correlation_id: PHASE4-POST-TRADE-001]
```

---

*POST_TRADE_REVIEW.md v1.0.0 | Phase 4 | 2025-07-27 | SOVEREIGN TIER*

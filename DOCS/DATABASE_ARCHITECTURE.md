# Database Architecture: Immutable Audit Log Schema

**Project:** Autonomous Alpha v1.3.2  
**Status:** HARDENED & VERIFIED  
**Assurance Level:** Sovereign Tier (100% Confidence)

---

## Executive Summary

The Immutable Audit Log Schema provides the foundational data persistence layer for Project Autonomous Alpha. It implements a blockchain-style audit trail within PostgreSQL, ensuring complete traceability of all trading signals, AI deliberations, and order executions.

**Sovereign Mandate:** Survival > Capital Preservation > Alpha

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        IMMUTABLE AUDIT LOG                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐   │
│   │   signals    │────▶│  ai_debates  │     │   order_execution    │   │
│   │  (ROOT)      │     │              │     │                      │   │
│   │              │─────┼──────────────┼────▶│                      │   │
│   └──────────────┘     └──────────────┘     └──────────┬───────────┘   │
│         │                                               │               │
│         │              correlation_id                   │               │
│         └───────────────────────────────────────────────┘               │
│                                                         │               │
│                                               ┌─────────▼───────────┐   │
│                                               │    order_events     │   │
│                                               │  (KILL_SWITCH,      │   │
│                                               │   FILLS, etc.)      │   │
│                                               └─────────────────────┘   │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                        SECURITY LAYERS                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 1: Trigger-based UPDATE/DELETE rejection (AUD-002 to AUD-007)    │
│  Layer 2: Permission-based denial (REVOKE UPDATE, DELETE)               │
│  Layer 3: SHA-256 hash chain tamper detection (AUD-009)                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tables

### signals (Root Table)

The entry point for all trade decision chains. Every webhook from TradingView creates a signal record.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| correlation_id | UUID | Chain anchor (auto-generated) |
| signal_id | VARCHAR(64) | TradingView signal ID (idempotency key) |
| symbol | VARCHAR(20) | Trading pair (e.g., BTCUSD) |
| side | VARCHAR(10) | BUY or SELL |
| price | DECIMAL(28,10) | Signal price |
| quantity | DECIMAL(28,10) | Signal quantity |
| raw_payload | JSONB | Complete webhook body (schema drift protection) |
| source_ip | INET | Webhook source IP |
| hmac_verified | BOOLEAN | HMAC-SHA256 verification status |
| row_hash | CHAR(64) | SHA-256 chain hash |
| created_at | TIMESTAMPTZ | Microsecond precision, UTC |

### ai_debates

Records AI model reasoning from the Cold Path.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| correlation_id | UUID | FK to signals |
| model_name | VARCHAR(50) | deepseek-r1, llama-3.1, phi-4, timeout |
| reasoning_json | JSONB | Model output (rejection reasons, sentiment) |
| confidence_score | DECIMAL(5,4) | 0.0000 to 1.0000 |
| elapsed_ms | INTEGER | Processing time |
| is_timeout | BOOLEAN | Cold Path timeout indicator |
| row_hash | CHAR(64) | SHA-256 chain hash |
| created_at | TIMESTAMPTZ | Microsecond precision, UTC |

### order_execution

Records trade orders submitted to the exchange.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| correlation_id | UUID | FK to signals |
| order_type | VARCHAR(20) | MARKET, LIMIT, STOP, STOP_LIMIT |
| symbol | VARCHAR(20) | Trading pair |
| side | VARCHAR(10) | BUY or SELL |
| quantity | DECIMAL(28,10) | Order quantity |
| price | DECIMAL(28,10) | Order price (NULL for MARKET) |
| exchange_order_id | VARCHAR(64) | Exchange-assigned ID |
| status | VARCHAR(20) | PENDING, SUBMITTED, FILLED, etc. |
| row_hash | CHAR(64) | SHA-256 chain hash |
| created_at | TIMESTAMPTZ | Microsecond precision, UTC |

### order_events

Append-only table for order lifecycle events.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| order_execution_id | BIGINT | FK to order_execution |
| event_type | VARCHAR(30) | FILL, PARTIAL_FILL, REJECTED, CANCELLED, KILL_SWITCH, EXPIRED |
| fill_quantity | DECIMAL(28,10) | Fill quantity |
| fill_price | DECIMAL(28,10) | Fill price |
| **zar_equity** | **DECIMAL(28,2)** | **ZAR equity at event time (KILL_SWITCH)** |
| positions_closed | JSONB | Positions closed (KILL_SWITCH) |
| rejection_reason | TEXT | Exchange rejection reason |
| exchange_error_code | VARCHAR(50) | Exchange error code |
| row_hash | CHAR(64) | SHA-256 chain hash |
| created_at | TIMESTAMPTZ | Microsecond precision, UTC |

---

## Views

### vw_trade_audit_full

Comprehensive view joining all tables via correlation_id. Provides single-row access to:

- Signal parameters and raw payload
- DeepSeek-R1 rejection reasoning
- Llama 3.1 sentiment analysis
- Combined AI confidence score
- Order execution details
- Latest order event (fills, rejections)
- **ZAR equity tracking**
- Chain of custody hashes

### vw_kill_switch_events

Specialized view for KILL_SWITCH audit trail showing:

- ZAR equity at trigger time
- All positions closed
- Original signal that led to the trade

---

## Security Model

### Defense in Depth

| Layer | Mechanism | Error Code |
|-------|-----------|------------|
| 1 | BEFORE UPDATE trigger | AUD-002, AUD-004, AUD-006 |
| 1 | BEFORE DELETE trigger | AUD-003, AUD-005, AUD-007 |
| 2 | REVOKE UPDATE, DELETE | Permission denied |
| 3 | Hash chain verification | AUD-009 (L6 Lockdown) |

### Application Role: app_trading

| Permission | signals | ai_debates | order_execution | order_events |
|------------|---------|------------|-----------------|--------------|
| SELECT | ✅ | ✅ | ✅ | ✅ |
| INSERT | ✅ | ✅ | ✅ | ✅ |
| UPDATE | ❌ | ❌ | ❌ | ❌ |
| DELETE | ❌ | ❌ | ❌ | ❌ |

---

## Chain of Custody

Every row contains a SHA-256 hash computed as:

```
row_hash = SHA-256(previous_row_hash || current_row_data)
```

The first row uses a predefined genesis hash. This creates a blockchain-style audit trail where any tampering breaks the chain and is detectable via `verify_chain_integrity()`.

---

## Error Codes

| Code | Condition | Action |
|------|-----------|--------|
| AUD-001 | Float precision loss detected | Reject transaction |
| AUD-002 | UPDATE on signals | Reject, log attempt |
| AUD-003 | DELETE on signals | Reject, log attempt |
| AUD-004 | UPDATE on ai_debates | Reject, log attempt |
| AUD-005 | DELETE on ai_debates | Reject, log attempt |
| AUD-006 | UPDATE on order_execution/order_events | Reject, log attempt |
| AUD-007 | DELETE on order_execution/order_events | Reject, log attempt |
| AUD-008 | Invalid correlation_id FK | Reject insert |
| AUD-009 | Hash chain mismatch | **L6 LOCKDOWN** |

---

## Verification Status

| Test | Result | Date |
|------|--------|------|
| DELETE Rejection (AUD-003) | ✅ PASSED | 2025-12-21 |
| UPDATE Rejection (AUD-002) | ✅ PASSED | 2025-12-21 |
| Hash Chain Integrity | ✅ PASSED | 2025-12-21 |

**SOVEREIGN MANDATE: IMMUTABILITY VERIFIED**

---

## Migration Files

| File | Purpose |
|------|---------|
| 001_core_functions.sql | Trigger functions, hash computation |
| 002_audit_tables.sql | Table definitions, constraints |
| 003_attach_triggers.sql | Trigger attachment |
| 004_security_hardening.sql | Permissions, views |

---

*Document Version: 1.3.2*  
*Last Updated: 2025-12-21*  
*Assurance Level: Sovereign Tier (100% Confidence)*

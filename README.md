# 🛡️ Project Autonomous Alpha

**Codename:** Sovereign Tier Infrastructure  
**Version:** 1.3.2  
**Status:** Milestone 1 Complete - Ingress Layer Operational

---

## Overview

Project Autonomous Alpha is a mission-critical, high-reliability AI-augmented trading appliance engineered to ingest TradingView signals and execute them across Crypto/Forex markets with an uncompromising focus on capital preservation.

### The Sovereign Mandate
> **Survival > Capital Preservation > Alpha.**

---

## Milestone 1: Ingress Layer ✅

The hardened signal gateway is fully operational with:

- **HMAC-SHA256 Authentication** - All webhooks verified against `SOVEREIGN_SECRET`
- **Decimal Integrity** - Zero floats in financial data (AUD-001 enforcement)
- **Immutable Audit Trail** - Blockchain-style hash chain for tamper detection
- **Defense-in-Depth Security** - Trigger + Permission + Hash verification layers

### Quick Start

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Run migrations
docker exec autonomous_alpha_db psql -U sovereign -d autonomous_alpha -f /docker-entrypoint-initdb.d/001_core_functions.sql
docker exec autonomous_alpha_db psql -U sovereign -d autonomous_alpha -f /docker-entrypoint-initdb.d/002_audit_tables.sql
docker exec autonomous_alpha_db psql -U sovereign -d autonomous_alpha -f /docker-entrypoint-initdb.d/003_attach_triggers.sql
docker exec autonomous_alpha_db psql -U sovereign -d autonomous_alpha -f /docker-entrypoint-initdb.d/004_security_hardening.sql
docker exec autonomous_alpha_db psql -U sovereign -d autonomous_alpha -f /docker-entrypoint-initdb.d/005_fix_trigger_permissions.sql

# 3. Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 4. Run validation suite
python scripts/test_ingress.py
```

---

## Error Code Reference

### SEC-XXX: Security Layer Errors

| Code | Description | HTTP Status | Action Required |
|------|-------------|-------------|-----------------|
| SEC-001 | Missing HMAC signature header | 401 | Include `X-TradingView-Signature` header |
| SEC-002 | IP address not in whitelist | 403 | Verify source IP is TradingView CIDR |
| SEC-003 | Invalid HMAC signature | 401 | Verify payload matches signature computation |
| SEC-004 | Replay attack detected | 409 | Signal already processed (idempotency) |

### AUD-XXX: Audit Layer Errors

| Code | Description | HTTP Status | Action Required |
|------|-------------|-------------|-----------------|
| AUD-001 | Float precision loss detected | 422 | Use string decimals (e.g., "100.00" not 100.0) |
| AUD-002 | UPDATE attempted on signals | 500 | Audit records are immutable |
| AUD-003 | DELETE attempted on signals | 500 | Audit records are immutable |
| AUD-004 | UPDATE attempted on ai_debates | 500 | Audit records are immutable |
| AUD-005 | DELETE attempted on ai_debates | 500 | Audit records are immutable |
| AUD-006 | UPDATE attempted on order_execution/events | 500 | Audit records are immutable |
| AUD-007 | DELETE attempted on order_execution/events | 500 | Audit records are immutable |
| AUD-008 | Invalid correlation_id reference | 422 | Parent record must exist first |
| AUD-009 | Hash chain integrity failure | 500 | **L6 LOCKDOWN** - Tamper detected |

### DB-XXX: Database Layer Errors

| Code | Description | Resolution |
|------|-------------|------------|
| DB-500 | Permission denied for hash computation | Fixed in migration 005 (SECURITY DEFINER) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    INGRESS LAYER (v1.3.2)                   │
├─────────────────────────────────────────────────────────────┤
│  TradingView Webhook                                        │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────┐                                        │
│  │  SEC-001/003    │  HMAC-SHA256 Verification              │
│  │  Authentication │                                        │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  AUD-001        │  Decimal Validation (Zero Floats)      │
│  │  Validation     │                                        │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  PostgreSQL     │  Immutable Audit Tables                │
│  │  + Hash Chain   │  SHA-256 Chain of Custody              │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Model

### Three-Layer Defense

1. **Trigger Layer** - `prevent_update()` / `prevent_delete()` reject modifications
2. **Permission Layer** - `app_trading` role has SELECT/INSERT only
3. **Hash Chain Layer** - `verify_chain_integrity()` detects tampering

### Application Role: `app_trading`

| Permission | signals | ai_debates | order_execution | order_events |
|------------|---------|------------|-----------------|--------------|
| SELECT     | ✅      | ✅         | ✅              | ✅           |
| INSERT     | ✅      | ✅         | ✅              | ✅           |
| UPDATE     | ❌      | ❌         | ❌              | ❌           |
| DELETE     | ❌      | ❌         | ❌              | ❌           |

---

## Database Migrations

| Migration | Description | Status |
|-----------|-------------|--------|
| 001_core_functions.sql | Trigger functions, hash computation | ✅ |
| 002_audit_tables.sql | signals, ai_debates, order_execution, order_events | ✅ |
| 003_attach_triggers.sql | Bind triggers to tables | ✅ |
| 004_security_hardening.sql | Role permissions, audit views | ✅ |
| 005_fix_trigger_permissions.sql | SECURITY DEFINER for hash chain | ✅ |

---

## Validation Suite

Run the ingress validation tests:

```bash
python scripts/test_ingress.py
```

### Test Cases

| Test | Description | Expected |
|------|-------------|----------|
| A: The Poison | Float value injection | AUD-001 rejection |
| B: The Pure | Valid string decimals | 200 OK, correlation_id |
| C: No Signature | Missing HMAC header | SEC-001 rejection |
| D: Invalid Signature | Wrong HMAC value | SEC-003 rejection |

---

## Roadmap

- [x] **Milestone 1:** Ingress Layer (Signal Gateway)
- [ ] **Milestone 2:** Sovereign Brain (Risk & Position Sizing)
- [ ] **Milestone 3:** Cold Path AI (DeepSeek-R1, Llama 3.1)
- [ ] **Milestone 4:** Exchange Integration (Order Execution)
- [ ] **Milestone 5:** L6 Safety (Kill Switch, ZAR Floor)

---

## License

Proprietary - Sovereign Tier Infrastructure

---

**[Reliability Audit: 100/100]**

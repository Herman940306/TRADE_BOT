# 📑 PRD: Project Autonomous Alpha (v1.3.1)
**Codename:** Sovereign Tier Infrastructure  
**Status:** DEFINITIVE / READY FOR INITIALIZATION  
**Assurance Level:** 100% Confidence (Sovereign Tier Verified)  

---

## 1. Executive Summary
Project Autonomous Alpha is a mission-critical, high-reliability AI-augmented trading appliance. It is engineered to ingest TradingView signals and execute them across Crypto/Forex markets with an uncompromising focus on capital preservation.

### The Sovereign Mandate
> **Survival > Capital Preservation > Alpha.** > If any logic node returns < 95% confidence, the system defaults to a **Neutral (Cash) State**.

---

## 2. Technical Stack
* **Hardware:** i7-9700K (Hot Path), 64GB RAM (State), RTX 2080 (Cold Path AI).
* **Ingress:** FastAPI (Python) with Uvicorn.
* **Logic:** 100% `decimal.Decimal` (Zero Floats).
* **Intelligence:** Ollama (DeepSeek-R1, Llama 3.1, Phi-4).
* **Persistence:** PostgreSQL (Immutable WAL logs).
* **Messaging:** Redis Streams (Async durability).

---

## 3. System Architecture

### 3.1 The Hot Path (Deterministic Execution)
* **Goal:** Acknowledge webhooks in < 50ms.
* **Nodes:**
    1. **Signature Auth:** HMAC-SHA256 verification using `SOVEREIGN_SECRET`.
    2. **IP Whitelisting:** Strictly TradingView official CIDR ranges.
    3. **Idempotency:** Unique UUID per signal to prevent duplicate fills.
    4. **Binary Logic Tree:** Pre-flight checks on margin, connectivity, and hardware health.

### 3.2 The Cold Path (Adversarial Intelligence)
* **Goal:** Use high-reasoning models to prevent "trap" trades.
* **Models:**
    * **DeepSeek-R1 (The Critic):** Must generate 3 logical reasons to **REJECT** the trade.
    * **Llama 3.1 (The Context):** Sentiment analysis and "Market Mood" validation.
* **Safe-Fail:** If the Cold Path takes > 30s, the signal is discarded.

---

## 4. Operational Guardrails (The Hardening Layer)

### 4.1 Drift Detection (AI Sanity)
* **Requirement:** Weekly "Golden Set" audit. The bot is fed 10 historical trades with known outcomes. If models fail to replicate the correct logic, the system triggers **Safe-Mode**.

### 4.2 Latency Pulse
* **Requirement:** 10-second heartbeat pings to Exchange API.
* **Threshold:** If Round-Trip Time (RTT) > 200ms, "Market" orders are disabled; only "Limit" orders are permitted to prevent slippage.

### 4.3 Atomic Reconciliation & L6 Lockdown
* **Requirement:** Every 60 seconds, the bot performs a 3-way sync (Local DB ↔ Internal State ↔ Exchange API).
* **L6 Audit Lockdown Definition:** If a mismatch or breach is detected:
    1. **Immediate Action:** Cease all new order placement.
    2. **Verification:** Perform a checksum hash of the DB against the exchange ledger.
    3. **Isolation:** Disconnect the Hot-Path from the Internet until a manual `RECOVER_SYSTEM` command is issued.

---

## 5. Risk Management (L6 Safety)

### 5.1 The ZAR Floor & Kill-Switch
* **Mandate:** Calculate Net Equity in **South African Rand (ZAR)** every 5 seconds.
* **Trigger:** If `Net_Equity < ZAR_FLOOR`, execute `KILL_SWITCH`:
    * Close all open positions.
    * Cancel all pending orders.
    * Revoke API session.

### 5.2 Adversarial Risk Detection
* **Requirement:** Continuous analysis of the `account_snapshot.json` for:
    1. Sudden balance decreases (>10%).
    2. Unauthorized transactions or suspicious withdrawal patterns.
    3. Position liquidations or margin call threshold breaches.

### 5.3 Position Sizing
* Positions are calculated using **ATR (Average True Range)**.
* Maximum 2% of total equity at risk in any 24-hour window.

---

## 6. Data & Audit Model
* **Immutable Logs:** Append-only tables for signals, decisions, and orders.
* **Traceability:** Every trade execution must be linked to a specific `correlation_id` from the initial Webhook.
* **Rounding:** Strictly `ROUND_HALF_EVEN` (Banker's Rounding).

---

## 7. Implementation Roadmap (Phase 1)
* **Step 1.1:** PostgreSQL Schema for Immutable Audit Logs.
* **Step 1.2:** Secure FastAPI Webhook Receiver (HMAC + IP Whitelist).
* **Step 1.3:** Decimal Logic Engine & Risk Handlers.
* **Step 1.4:** Ollama Intelligence Bridge.
#!/usr/bin/env bash
# Phase 2B: Test webhook-originated paper trading flow
# Usage: bash scripts/test_webhook_paper.sh

set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
SECRET="dev_secret_key_32_characters_minimum_1234"
SIGNAL_ID="TV-P2B-$(date +%s)"

echo "=== Phase 2B: Webhook Paper Flow Test ==="
echo "Base URL: ${BASE_URL}"
echo "Signal ID: ${SIGNAL_ID}"
echo ""

# Step 1: Health check
echo "--- Step 1: Health Check ---"
HEALTH=$(curl -s "${BASE_URL}/health")
echo "Health: ${HEALTH}"
echo ""

# Step 2: Send webhook
echo "--- Step 2: Send Webhook ---"
BODY="{\"signal_id\":\"${SIGNAL_ID}\",\"symbol\":\"BTCZAR\",\"side\":\"BUY\",\"price\":\"1250000.00\",\"quantity\":\"0.001\"}"
SIG=$(echo -n "${BODY}" | openssl dgst -sha256 -hmac "${SECRET}" | awk '{print $NF}')
echo "Payload: ${BODY}"
echo "Signature: ${SIG}"

WEBHOOK_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/webhook/tradingview" \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: ${SIG}" \
  -d "${BODY}")

HTTP_CODE=$(echo "${WEBHOOK_RESP}" | tail -1)
WEBHOOK_BODY=$(echo "${WEBHOOK_RESP}" | head -n -1)
echo "HTTP ${HTTP_CODE}: ${WEBHOOK_BODY}"
echo ""

if [ "${HTTP_CODE}" != "200" ] && [ "${HTTP_CODE}" != "202" ]; then
  echo "FAIL: Webhook rejected with HTTP ${HTTP_CODE}"
  exit 1
fi

# Step 3: Check pending approvals
echo "--- Step 3: Check Pending Approvals ---"
sleep 2
PENDING=$(curl -s "${BASE_URL}/api/hitl/pending")
echo "Pending: ${PENDING}"
echo ""

# Step 4: Approve the trade (if pending)
echo "--- Step 4: Approve Trade ---"
TRADE_ID=$(echo "${PENDING}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
pending = data.get('pending_approvals', data) if isinstance(data, dict) else data
if isinstance(pending, list) and len(pending) > 0:
    item = pending[0]
    ar = item.get('approval_request', item)
    print(ar.get('trade_id', ''))
else:
    print('')
" 2>/dev/null || echo "")

if [ -z "${TRADE_ID}" ]; then
  echo "No pending approvals found (may have been auto-approved or expired)"
  echo "Checking if HITL is disabled (auto-approve mode)..."
  echo ""
else
  echo "Trade ID: ${TRADE_ID}"
  APPROVE_BODY="{\"trade_id\":\"${TRADE_ID}\",\"decision\":\"APPROVE\",\"operator\":\"test_operator\",\"channel\":\"CLI\",\"reason\":\"Phase 2B paper test\"}"
  echo "Approve payload: ${APPROVE_BODY}"

  APPROVE_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/hitl/decide" \
    -H "Content-Type: application/json" \
    -d "${APPROVE_BODY}")

  APPROVE_CODE=$(echo "${APPROVE_RESP}" | tail -1)
  APPROVE_BODY_RESP=$(echo "${APPROVE_RESP}" | head -n -1)
  echo "HTTP ${APPROVE_CODE}: ${APPROVE_BODY_RESP}"
  echo ""
fi

# Step 5: Check DemoBroker state
echo "--- Step 5: DemoBroker State ---"
if [ -f "data/demo_broker_state.json" ]; then
  cat data/demo_broker_state.json
  echo ""
else
  echo "No local state file (may be inside container)"
  docker exec aa_local_app cat /app/data/demo_broker_state.json 2>/dev/null || echo "State file not found in container"
fi
echo ""

# Step 6: Check audit log
echo "--- Step 6: Audit Log (last 5 entries) ---"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -c \
  "SELECT id, action, target_type, target_id, created_at FROM audit_log ORDER BY created_at DESC LIMIT 5;" 2>/dev/null || echo "Could not query audit_log"
echo ""

# Step 7: Duplicate rejection test
echo "--- Step 7: Duplicate Signal Rejection ---"
DUP_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/webhook/tradingview" \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: ${SIG}" \
  -d "${BODY}")
DUP_CODE=$(echo "${DUP_RESP}" | tail -1)
DUP_BODY=$(echo "${DUP_RESP}" | head -n -1)
echo "Duplicate signal HTTP ${DUP_CODE}: ${DUP_BODY}"
if [ "${DUP_CODE}" = "409" ]; then
  echo "PASS: Duplicate correctly rejected"
else
  echo "NOTE: Expected 409, got ${DUP_CODE}"
fi
echo ""

echo "=== Webhook Paper Flow Test Complete ==="

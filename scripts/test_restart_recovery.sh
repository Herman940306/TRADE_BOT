#!/usr/bin/env bash
# Phase 2B: Recovery/restart validation
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"

echo "=== Phase 2B: Recovery/Restart Validation ==="
echo ""

# Pre-restart snapshot
echo "--- Pre-Restart State ---"
echo "DB counts:"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -t -c \
  "SELECT 'hitl_approvals=' || COUNT(*) FROM hitl_approvals;"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -t -c \
  "SELECT 'audit_log=' || COUNT(*) FROM audit_log;"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -t -c \
  "SELECT 'signals=' || COUNT(*) FROM signals;"

echo ""
echo "DemoBroker state file:"
docker exec aa_local_app python3 -c "
import json
with open('/app/data/demo_broker_state.json') as f:
    d = json.load(f)
print(f'  Positions: {len(d.get(\"positions\", {}))}')
print(f'  Orders: {len(d.get(\"orders\", {}))}')
print(f'  Balance: {d.get(\"balance_zar\", \"N/A\")}')
" 2>/dev/null || echo "  No state file"

echo ""
echo "Health: $(curl -s ${BASE_URL}/health)"
echo ""

# Scenario 1: App restart (keep DB running)
echo "--- Scenario 1: App Container Restart ---"
docker restart aa_local_app
echo "Waiting for recovery..."
sleep 15

# Check health
HEALTH=$(curl -s "${BASE_URL}/health" 2>/dev/null || echo "NOT_READY")
echo "Health after restart: ${HEALTH}"

# Check for SEC-080 errors
echo "SEC-080 errors in logs:"
SEC080=$(docker logs aa_local_app 2>&1 | grep -c "SEC-080" || echo "0")
echo "  Count: ${SEC080}"
echo ""

# Scenario 2: Full stack restart (DB + App)
echo "--- Scenario 2: Full Stack Restart ---"
cd /mnt/d/dev/repos/TRADE_BOT
docker compose -f docker-compose.local.yml restart
echo "Waiting for full recovery..."
sleep 30

HEALTH2=$(curl -s "${BASE_URL}/health" 2>/dev/null || echo "NOT_READY")
echo "Health after full restart: ${HEALTH2}"
echo ""

# Post-restart verification
echo "--- Post-Restart Verification ---"
echo "DB counts:"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -t -c \
  "SELECT 'hitl_approvals=' || COUNT(*) FROM hitl_approvals;"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -t -c \
  "SELECT 'audit_log=' || COUNT(*) FROM audit_log;"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -t -c \
  "SELECT 'signals=' || COUNT(*) FROM signals;"

echo ""
echo "DemoBroker state recovered:"
docker exec aa_local_app python3 -c "
import json
with open('/app/data/demo_broker_state.json') as f:
    d = json.load(f)
print(f'  Positions: {len(d.get(\"positions\", {}))}')
print(f'  Orders: {len(d.get(\"orders\", {}))}')
print(f'  Balance: {d.get(\"balance_zar\", \"N/A\")}')
" 2>/dev/null || echo "  No state file"

echo ""
echo "Guardian status: $(curl -s ${BASE_URL}/guardian/status 2>/dev/null || echo 'NOT_READY')"
echo ""

# Scenario 3: Duplicate rejection after restart
echo "--- Scenario 3: Duplicate Rejection After Restart ---"
SECRET="dev_secret_key_32_characters_minimum_1234"
DUP_BODY='{"signal_id":"TV-P2B-1774764674","symbol":"BTCZAR","side":"BUY","price":"1250000.00","quantity":"0.001"}'
DUP_SIG=$(echo -n "${DUP_BODY}" | openssl dgst -sha256 -hmac "${SECRET}" | awk '{print $NF}')
DUP_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/webhook/tradingview" \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: ${DUP_SIG}" \
  -d "${DUP_BODY}")
DUP_CODE=$(echo "${DUP_RESP}" | tail -1)
DUP_BODY_RESP=$(echo "${DUP_RESP}" | head -n -1)
echo "Duplicate signal HTTP ${DUP_CODE}: ${DUP_BODY_RESP}"
if [ "${DUP_CODE}" = "409" ]; then
  echo "PASS: Duplicate correctly rejected after restart"
else
  echo "NOTE: Expected 409, got ${DUP_CODE}"
fi
echo ""

echo "=== Recovery/Restart Validation Complete ==="

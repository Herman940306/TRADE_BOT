#!/usr/bin/env bash
# Phase 1 webhook test script

PAYLOAD='{"signal_id": "TEST-PHASE1-001", "symbol": "BTCZAR", "side": "BUY", "price": "1250000.50", "quantity": "0.001"}'
SIG="664374b319498e5fdffdb2cd72793048f3a6adcf0993397601eeb574e64c49f4"

echo "=== Sending valid webhook ==="
echo "Payload: $PAYLOAD"
echo "Signature: $SIG"
echo ""

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST http://localhost:8080/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: $SIG" \
  -d "$PAYLOAD"

echo ""
echo "=== Done ==="

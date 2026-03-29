#!/usr/bin/env bash
# Phase 1 invalid webhook test - expect 401

PAYLOAD='{"signal_id": "TEST-PHASE1-002", "symbol": "BTCZAR", "side": "BUY", "price": "1250000.50", "quantity": "0.001"}'
SIG="0000000000000000000000000000000000000000000000000000000000000000"

echo "=== Sending INVALID webhook (wrong signature) ==="
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST http://localhost:8080/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: $SIG" \
  -d "$PAYLOAD"

echo ""
echo "=== Sending INVALID webhook (missing signature) ==="
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST http://localhost:8080/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

echo ""
echo "=== Done ==="

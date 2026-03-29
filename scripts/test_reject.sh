#!/usr/bin/env bash
# Phase 1: Reject a pending HITL trade

TRADE_ID="$1"

if [ -z "$TRADE_ID" ]; then
  echo "Usage: bash test_reject.sh <trade_id>"
  exit 1
fi

echo "=== Rejecting trade $TRADE_ID ==="
curl -s -X POST "http://localhost:8080/api/hitl/${TRADE_ID}/reject" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev_operator1" \
  -d '{"rejected_by": "dev_operator1", "channel": "WEB", "reason": "Phase 1 test rejection - not a real trade"}' | python3 -m json.tool

echo ""
echo "=== Done ==="

#!/usr/bin/env bash
# Phase 1: Approve a pending HITL trade

TRADE_ID="$1"

if [ -z "$TRADE_ID" ]; then
  echo "Usage: bash test_approve_v2.sh <trade_id>"
  exit 1
fi

echo "=== Approving trade $TRADE_ID ==="
curl -s -X POST "http://localhost:8080/api/hitl/${TRADE_ID}/approve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev_operator1" \
  -d '{"approved_by": "dev_operator1", "channel": "WEB", "comment": "Phase 1 test approval"}' | python3 -m json.tool

echo ""
echo "=== Done ==="

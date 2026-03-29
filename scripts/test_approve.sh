#!/usr/bin/env bash
# Phase 1: Approve a pending HITL trade

TRADE_ID="87abf84b-056c-4b16-856b-7fddc5c050af"

echo "=== Approving trade $TRADE_ID ==="
RESPONSE=$(curl -s -o /dev/stdout -w "\n---HTTP_CODE:%{http_code}" \
  -X POST "http://localhost:8080/api/hitl/${TRADE_ID}/approve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev_operator1" \
  -d '{"approved_by": "dev_operator1", "channel": "WEB", "comment": "Phase 1 test approval"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1 | sed 's/---HTTP_CODE://')
BODY=$(echo "$RESPONSE" | sed '$ d')

echo "HTTP Status: $HTTP_CODE"
echo "$BODY" | python3 -m json.tool

echo ""
echo "=== Done ==="

#!/usr/bin/env bash
echo "=== HITL Approvals ==="
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "SELECT id, trade_id, instrument, side, status, request_price, requested_at, expires_at FROM hitl_approvals ORDER BY requested_at DESC LIMIT 10;"

echo ""
echo "=== Signals ==="
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "SELECT id, signal_id, symbol, side, price, quantity, created_at FROM signals ORDER BY created_at DESC LIMIT 5;"

echo ""
echo "=== Audit Log (last 5) ==="
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "SELECT id, actor_id, action, target_type, created_at FROM audit_log ORDER BY created_at DESC LIMIT 5;"

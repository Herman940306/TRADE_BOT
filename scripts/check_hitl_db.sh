#!/usr/bin/env bash
echo "=== HITL Approvals (full) ==="
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "SELECT id, trade_id, status, row_hash IS NOT NULL as has_hash FROM hitl_approvals ORDER BY requested_at DESC LIMIT 10;"

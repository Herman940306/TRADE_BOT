#!/usr/bin/env bash
# Clean test data from hitl_approvals and restart
echo "=== Cleaning test HITL data ==="
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "DELETE FROM hitl_approvals;"
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "DELETE FROM audit_log;"
echo "=== DB cleaned ==="

echo ""
echo "=== Rebuilding app container ==="
docker compose -f docker-compose.local.yml up -d --build app 2>&1
echo ""
echo "=== Waiting for app to start ==="
sleep 20

echo ""
echo "=== Health check ==="
curl -s http://localhost:8080/health
echo ""

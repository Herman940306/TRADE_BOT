#!/usr/bin/env bash
# Phase 2B: Guardian lock/unlock validation
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"

echo "=== Phase 2B: Guardian Lock/Unlock Validation ==="
echo ""

# Step 1: Check initial state (should be unlocked)
echo "--- Step 1: Initial Guardian Status ---"
STATUS=$(curl -s "${BASE_URL}/guardian/status")
echo "${STATUS}" | python3 -m json.tool 2>/dev/null || echo "${STATUS}"
echo ""

# Step 2: Simulate Guardian lock via lock file inside container
echo "--- Step 2: Simulate Guardian Lock ---"
docker exec aa_local_app bash -c 'mkdir -p /app/data && python3 -c "
import json, uuid
from datetime import datetime, timezone
lock_event = {
    \"lock_id\": str(uuid.uuid4()),
    \"locked_at\": datetime.now(timezone.utc).isoformat(),
    \"reason\": \"Phase 2B test: simulated loss limit breach\",
    \"lock_type\": \"HARD_STOP\",
    \"daily_pnl_zar\": \"-1500.00\",
    \"loss_limit_zar\": \"1000.00\"
}
with open(\"/app/data/guardian_lock.json\", \"w\") as f:
    json.dump(lock_event, f, indent=2)
print(\"Lock file created:\", json.dumps(lock_event, indent=2))
"'
echo ""

# Step 3: Check that Guardian reports locked status
echo "--- Step 3: Guardian Status After Lock ---"
# Note: The Guardian may need to re-read the lock file on next check_vitals
# Let's call status endpoint
STATUS_LOCKED=$(curl -s "${BASE_URL}/guardian/status")
echo "${STATUS_LOCKED}" | python3 -m json.tool 2>/dev/null || echo "${STATUS_LOCKED}"
echo ""

# Step 4: Try to reach HITL (should be blocked by Guardian)
echo "--- Step 4: Test HITL Pending (Guardian Lock Check) ---"
PENDING_RESP=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/hitl/pending" \
  -H "Authorization: Bearer test_operator")
PENDING_CODE=$(echo "${PENDING_RESP}" | tail -1)
PENDING_BODY=$(echo "${PENDING_RESP}" | head -n -1)
echo "HTTP ${PENDING_CODE}: ${PENDING_BODY}"
echo ""

# Step 5: Unlock via API
echo "--- Step 5: Unlock Guardian ---"
ADMIN_TOKEN="${GUARDIAN_ADMIN_TOKEN:-admin_secret_token}"
UNLOCK_BODY='{"reason":"Phase 2B test unlock","correlation_id":"p2b-unlock-test-001"}'
UNLOCK_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/guardian/unlock" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d "${UNLOCK_BODY}")
UNLOCK_CODE=$(echo "${UNLOCK_RESP}" | tail -1)
UNLOCK_BODY_RESP=$(echo "${UNLOCK_RESP}" | head -n -1)
echo "HTTP ${UNLOCK_CODE}: ${UNLOCK_BODY_RESP}"
echo ""

# Step 6: Verify Guardian is unlocked
echo "--- Step 6: Guardian Status After Unlock ---"
STATUS_UNLOCKED=$(curl -s "${BASE_URL}/guardian/status")
echo "${STATUS_UNLOCKED}" | python3 -m json.tool 2>/dev/null || echo "${STATUS_UNLOCKED}"
echo ""

# Step 7: Check lock file is removed
echo "--- Step 7: Lock File State ---"
docker exec aa_local_app bash -c 'if [ -f /app/data/guardian_lock.json ]; then echo "Lock file exists: $(cat /app/data/guardian_lock.json)"; else echo "Lock file removed - correct"; fi'
echo ""

echo "=== Guardian Lock/Unlock Test Complete ==="

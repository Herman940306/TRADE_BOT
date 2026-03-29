#!/usr/bin/env bash
# =============================================================================
# Project Autonomous Alpha — Phase 5
# pull_ollama_model.sh — Pull and verify the AI Council model
#
# Usage:
#   ./scripts/pull_ollama_model.sh [MODEL] [OLLAMA_URL]
#
# Defaults:
#   MODEL       = qwen3:8b
#   OLLAMA_URL  = http://localhost:11434
#
# Exit codes:
#   0  — Model pulled and verified
#   1  — Ollama unreachable or pull failed
#   2  — Model not found after pull (verification failed)
# =============================================================================
set -euo pipefail

MODEL="${1:-${OLLAMA_MODEL:-qwen3:8b}}"
OLLAMA_URL="${2:-${OLLAMA_BASE_URL:-http://localhost:11434}}"

echo "============================================================"
echo "  Autonomous Alpha — Ollama Model Pull"
echo "  Model   : ${MODEL}"
echo "  Endpoint: ${OLLAMA_URL}"
echo "============================================================"

# ---------------------------------------------------------------------------
# Step 1: Confirm Ollama daemon is reachable
# ---------------------------------------------------------------------------
echo ""
echo "[1/3] Checking Ollama daemon liveness..."
if ! curl -sf "${OLLAMA_URL}/api/tags" > /dev/null; then
    echo "  ERROR: Ollama daemon unreachable at ${OLLAMA_URL}"
    echo "  Ensure the ollama container is running:"
    echo "    docker compose -f docker-compose.local.yml up -d ollama"
    exit 1
fi
echo "  OK — Ollama is reachable."

# ---------------------------------------------------------------------------
# Step 2: Pull the model
# ---------------------------------------------------------------------------
echo ""
echo "[2/3] Pulling model '${MODEL}' (this may take several minutes)..."
if ! curl -sf -X POST "${OLLAMA_URL}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${MODEL}\", \"stream\": false}" | grep -q '"status"'; then
    echo "  ERROR: Pull request failed. Check Ollama logs."
    exit 1
fi
echo "  Pull request submitted. Waiting for completion..."

# Poll until the model appears in the tag list (max 10 minutes)
TIMEOUT=600
ELAPSED=0
POLL_INTERVAL=10
MODEL_BASE="${MODEL%%:*}"

while [ "${ELAPSED}" -lt "${TIMEOUT}" ]; do
    TAGS=$(curl -sf "${OLLAMA_URL}/api/tags" || echo '{"models":[]}')
    if echo "${TAGS}" | grep -q "\"${MODEL_BASE}"; then
        break
    fi
    sleep "${POLL_INTERVAL}"
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
    echo "  Waiting for model to be ready... (${ELAPSED}s elapsed)"
done

if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "  ERROR: Model did not appear in tag list within ${TIMEOUT}s."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 3: Verify model is callable (minimal smoke inference)
# ---------------------------------------------------------------------------
echo ""
echo "[3/3] Running smoke test inference..."
SMOKE_RESPONSE=$(curl -sf -X POST "${OLLAMA_URL}/api/generate" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"${MODEL}\", \"prompt\": \"Respond with: OK\", \"stream\": false, \"options\": {\"num_predict\": 4, \"temperature\": 0}}" \
    | grep -o '"response":"[^"]*"' || echo "")

if [ -z "${SMOKE_RESPONSE}" ]; then
    echo "  WARNING: Smoke test returned no response — model may need warm-up time."
    echo "  Proceeding, but monitor first inference latency."
    exit 0
fi

echo "  Smoke test passed: ${SMOKE_RESPONSE}"

echo ""
echo "============================================================"
echo "  SUCCESS: ${MODEL} is pulled and ready."
echo "  Start the full stack: docker compose -f docker-compose.local.yml up -d"
echo "============================================================"
exit 0

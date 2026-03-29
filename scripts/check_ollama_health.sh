#!/usr/bin/env bash
# =============================================================================
# Project Autonomous Alpha — Phase 5
# check_ollama_health.sh — Diagnostics for the Ollama service
#
# Usage:
#   ./scripts/check_ollama_health.sh [OLLAMA_URL] [MODEL]
#
# Defaults:
#   OLLAMA_URL = http://localhost:11434
#   MODEL      = qwen3:8b
#
# Exit codes:
#   0  — All checks passed (healthy)
#   1  — One or more checks failed (degraded)
# =============================================================================
set -uo pipefail

OLLAMA_URL="${1:-${OLLAMA_BASE_URL:-http://localhost:11434}}"
MODEL="${2:-${OLLAMA_MODEL:-qwen3:8b}}"
MODEL_BASE="${MODEL%%:*}"
PASS=0
FAIL=0

_ok()  { echo "  [PASS] $*"; PASS=$((PASS + 1)); }
_err() { echo "  [FAIL] $*"; FAIL=$((FAIL + 1)); }

echo "============================================================"
echo "  Autonomous Alpha — Ollama Health Check"
echo "  Endpoint: ${OLLAMA_URL}"
echo "  Model   : ${MODEL}"
echo "============================================================"

# ---------------------------------------------------------------------------
# Check 1: Liveness — daemon reachable
# ---------------------------------------------------------------------------
echo ""
echo "[1] Daemon liveness (GET /api/tags)..."
if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
    _ok "Ollama daemon is reachable."
else
    _err "Ollama daemon is NOT reachable at ${OLLAMA_URL}."
fi

# ---------------------------------------------------------------------------
# Check 2: Readiness — model listed in tag registry
# ---------------------------------------------------------------------------
echo ""
echo "[2] Model readiness ('${MODEL}' in /api/tags)..."
TAGS=$(curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null || echo '{"models":[]}')
if echo "${TAGS}" | grep -q "\"${MODEL_BASE}"; then
    _ok "Model '${MODEL_BASE}' is listed."
else
    _err "Model '${MODEL_BASE}' is NOT listed. Run: bash scripts/pull_ollama_model.sh"
fi

# ---------------------------------------------------------------------------
# Check 3: Functional smoke test — minimal inference call
# ---------------------------------------------------------------------------
echo ""
echo "[3] Smoke test inference (minimal prompt)..."
SMOKE=$(curl -sf --max-time 90 -X POST "${OLLAMA_URL}/api/generate" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"${MODEL}\", \"prompt\": \"Respond with: OK\", \"stream\": false, \"options\": {\"num_predict\": 4, \"temperature\": 0}}" \
    2>/dev/null || echo "")

if echo "${SMOKE}" | grep -q '"response"'; then
    RESPONSE_VAL=$(echo "${SMOKE}" | grep -o '"response":"[^"]*"' | head -1)
    _ok "Smoke test passed: ${RESPONSE_VAL}"
else
    _err "Smoke test failed — no 'response' field in output."
    echo "     Raw output (truncated): ${SMOKE:0:200}"
fi

# ---------------------------------------------------------------------------
# Check 4: GPU status (informational, non-fatal)
# ---------------------------------------------------------------------------
echo ""
echo "[4] GPU acceleration status (informational)..."
if command -v nvidia-smi > /dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    GPU_MEM=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    _ok "NVIDIA GPU detected: ${GPU_NAME} | VRAM used: ${GPU_MEM}"
else
    echo "  [INFO] nvidia-smi not found — running on CPU (expected for local dev)."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Results: ${PASS} passed, ${FAIL} failed"
if [ "${FAIL}" -eq 0 ]; then
    echo "  STATUS: HEALTHY — AI Council is ready."
    echo "============================================================"
    exit 0
else
    echo "  STATUS: DEGRADED — resolve failures before live trading."
    echo "============================================================"
    exit 1
fi

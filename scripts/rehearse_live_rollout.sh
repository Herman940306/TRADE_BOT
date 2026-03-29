#!/usr/bin/env bash
# ============================================================================
# Project Autonomous Alpha — Operational Dry Rehearsal
# ============================================================================
#
# Purpose:  Walk through every operational step required for a first live
#           trade WITHOUT placing a real order. Validates that all systems
#           are configured, accessible, and healthy.
#
# Usage:    bash scripts/rehearse_live_rollout.sh
#           (Run from WSL inside the TRADE_BOT directory)
#
# Exit:     0 = all checks passed
#           1 = one or more checks failed
#
# Phase:    4 — Operational Funding & First Live Trade Readiness
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { ((PASS++)); echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { ((FAIL++)); echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { ((WARN++)); echo -e "  ${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "  ${CYAN}[INFO]${NC} $1"; }

echo ""
echo "============================================================================"
echo " Autonomous Alpha — Operational Dry Rehearsal"
echo " Phase 4: First Live Trade Readiness"
echo "============================================================================"
echo ""

# ============================================================================
# Section 1: Environment File Checks
# ============================================================================

echo -e "${CYAN}--- Section 1: Environment File ---${NC}"

if [ -f ".env" ]; then
    pass ".env file exists"
else
    fail ".env file not found — copy from .env.live.example"
fi

if [ -f ".env" ] && grep -q "VALR_API_KEY=" .env 2>/dev/null; then
    VAL=$(grep "VALR_API_KEY=" .env | head -1 | cut -d'=' -f2-)
    if [ -n "$VAL" ] && [ "$VAL" != "your_valr_api_key_here" ] && [ "$VAL" != "<YOUR_VALR_API_KEY>" ]; then
        pass "VALR_API_KEY is set (non-placeholder)"
    else
        fail "VALR_API_KEY is a placeholder — set your real key"
    fi
else
    fail "VALR_API_KEY not found in .env"
fi

if [ -f ".env" ] && grep -q "VALR_API_SECRET=" .env 2>/dev/null; then
    VAL=$(grep "VALR_API_SECRET=" .env | head -1 | cut -d'=' -f2-)
    if [ -n "$VAL" ] && [ "$VAL" != "your_valr_api_secret_here" ] && [ "$VAL" != "<YOUR_VALR_API_SECRET>" ]; then
        pass "VALR_API_SECRET is set (non-placeholder)"
    else
        fail "VALR_API_SECRET is a placeholder — set your real secret"
    fi
else
    fail "VALR_API_SECRET not found in .env"
fi

if [ -f ".env" ] && grep -q "SOVEREIGN_SECRET=" .env 2>/dev/null; then
    VAL=$(grep "SOVEREIGN_SECRET=" .env | head -1 | cut -d'=' -f2-)
    LEN=${#VAL}
    if [ "$LEN" -ge 32 ]; then
        pass "SOVEREIGN_SECRET is set (${LEN} chars)"
    else
        fail "SOVEREIGN_SECRET too short (${LEN} chars, need >= 32)"
    fi
else
    fail "SOVEREIGN_SECRET not found in .env"
fi

if [ -f ".env" ] && grep -q "HITL_ALLOWED_OPERATORS=" .env 2>/dev/null; then
    VAL=$(grep "HITL_ALLOWED_OPERATORS=" .env | head -1 | cut -d'=' -f2-)
    if [ -n "$VAL" ] && [ "$VAL" != "<YOUR_OPERATOR_ID>" ]; then
        pass "HITL_ALLOWED_OPERATORS is set: ${VAL}"
    else
        fail "HITL_ALLOWED_OPERATORS is empty or placeholder"
    fi
else
    fail "HITL_ALLOWED_OPERATORS not found in .env"
fi

if [ -f ".env" ] && grep -q "DB_PASSWORD=" .env 2>/dev/null; then
    VAL=$(grep "DB_PASSWORD=" .env | head -1 | cut -d'=' -f2-)
    if [ "$VAL" = "trading_app_2024" ]; then
        fail "DB_PASSWORD is still the insecure default"
    else
        pass "DB_PASSWORD has been changed from default"
    fi
else
    warn "DB_PASSWORD not found in .env (will use default — insecure)"
fi

if [ -f ".env" ] && grep -q "GUARDIAN_ADMIN_TOKEN=" .env 2>/dev/null; then
    VAL=$(grep "GUARDIAN_ADMIN_TOKEN=" .env | head -1 | cut -d'=' -f2-)
    if [ -n "$VAL" ] && [ "$VAL" != "<GENERATE_UNIQUE_SECRET>" ]; then
        pass "GUARDIAN_ADMIN_TOKEN is set"
    else
        fail "GUARDIAN_ADMIN_TOKEN is empty or placeholder"
    fi
else
    fail "GUARDIAN_ADMIN_TOKEN not found in .env"
fi

if [ -f ".env" ] && grep -q "ZAR_FLOOR=" .env 2>/dev/null; then
    VAL=$(grep "ZAR_FLOOR=" .env | head -1 | cut -d'=' -f2-)
    if [ -n "$VAL" ] && [ "$VAL" != "<YOUR_FUNDED_EQUITY_ZAR>" ]; then
        pass "ZAR_FLOOR is set: R${VAL}"
    else
        fail "ZAR_FLOOR is empty or placeholder"
    fi
else
    warn "ZAR_FLOOR not found in .env (will use R100,000 default)"
fi

echo ""

# ============================================================================
# Section 2: Git Safety
# ============================================================================

echo -e "${CYAN}--- Section 2: Git Safety ---${NC}"

if [ -f ".gitignore" ]; then
    if grep -q "\.env" .gitignore 2>/dev/null; then
        pass ".env is in .gitignore"
    else
        fail ".env is NOT in .gitignore — credentials at risk!"
    fi
else
    fail ".gitignore not found"
fi

if git status --porcelain .env 2>/dev/null | grep -q "^"; then
    fail ".env is tracked by git — remove it immediately"
else
    pass ".env is not tracked by git"
fi

echo ""

# ============================================================================
# Section 3: Docker Stack
# ============================================================================

echo -e "${CYAN}--- Section 3: Docker Stack ---${NC}"

if command -v docker &>/dev/null; then
    pass "Docker is available"
else
    fail "Docker not found in PATH"
fi

if docker compose version &>/dev/null; then
    pass "Docker Compose is available"
else
    fail "Docker Compose not found"
fi

if [ -f "docker-compose.local.yml" ]; then
    pass "docker-compose.local.yml exists"
else
    fail "docker-compose.local.yml not found"
fi

# Check if stack is running
RUNNING=$(docker compose -f docker-compose.local.yml ps --format json 2>/dev/null | head -1 || echo "")
if [ -n "$RUNNING" ]; then
    pass "Docker stack has running containers"
else
    warn "Docker stack is not running — start with: docker compose -f docker-compose.local.yml up -d"
fi

echo ""

# ============================================================================
# Section 4: Application Health (if stack is running)
# ============================================================================

echo -e "${CYAN}--- Section 4: Application Health ---${NC}"

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null || echo "000")
if [ "$HEALTH" = "200" ]; then
    pass "Health endpoint responds (HTTP 200)"
else
    warn "Health endpoint not reachable (HTTP ${HEALTH}) — is the stack running?"
fi

GUARDIAN=$(curl -s http://localhost:8080/guardian/status 2>/dev/null || echo "{}")
if echo "$GUARDIAN" | grep -q '"locked"'; then
    LOCKED=$(echo "$GUARDIAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('locked', 'unknown'))" 2>/dev/null || echo "unknown")
    if [ "$LOCKED" = "False" ] || [ "$LOCKED" = "false" ]; then
        pass "Guardian is unlocked"
    elif [ "$LOCKED" = "True" ] || [ "$LOCKED" = "true" ]; then
        fail "Guardian is LOCKED — unlock before live trading"
    else
        warn "Guardian status unclear: ${LOCKED}"
    fi
else
    warn "Guardian status endpoint not reachable"
fi

echo ""

# ============================================================================
# Section 5: Diagnostic Scripts
# ============================================================================

echo -e "${CYAN}--- Section 5: Diagnostic Scripts ---${NC}"

if [ -f "scripts/check_exchange_connectivity.py" ]; then
    pass "check_exchange_connectivity.py exists"
else
    fail "check_exchange_connectivity.py not found"
fi

if [ -f "scripts/check_live_readiness.py" ]; then
    pass "check_live_readiness.py exists"
else
    fail "check_live_readiness.py not found"
fi

if [ -f "scripts/validate_live_path.py" ]; then
    pass "validate_live_path.py exists"
else
    fail "validate_live_path.py not found"
fi

if [ -f "scripts/kill_switch.py" ]; then
    pass "kill_switch.py exists"
else
    fail "kill_switch.py not found"
fi

echo ""

# ============================================================================
# Section 6: Documentation
# ============================================================================

echo -e "${CYAN}--- Section 6: Documentation ---${NC}"

for doc in \
    "DOCS/PRODUCTION_ENV_REQUIREMENTS.md" \
    "DOCS/VALR_ONBOARDING_CHECKLIST.md" \
    "DOCS/FUNDING_RUNBOOK.md" \
    "DOCS/FIRST_LIVE_TRADE_CHECKLIST.md" \
    "DOCS/POST_TRADE_REVIEW.md" \
    "LIVE_EXECUTION_RUNBOOK.md"; do
    if [ -f "$doc" ]; then
        pass "$doc exists"
    else
        fail "$doc not found"
    fi
done

echo ""

# ============================================================================
# Section 7: Mode Safety Verification
# ============================================================================

echo -e "${CYAN}--- Section 7: Mode Safety ---${NC}"

if [ -f ".env" ]; then
    EXEC_MODE=$(grep "^EXECUTION_MODE=" .env 2>/dev/null | head -1 | cut -d'=' -f2- || echo "")
    if [ "$EXEC_MODE" = "LIVE" ]; then
        warn "EXECUTION_MODE is already LIVE — this rehearsal does not place orders"
    elif [ "$EXEC_MODE" = "LIVE_READ_ONLY" ]; then
        pass "EXECUTION_MODE is LIVE_READ_ONLY (safe for rehearsal)"
    elif [ "$EXEC_MODE" = "DEMO" ] || [ -z "$EXEC_MODE" ]; then
        pass "EXECUTION_MODE is DEMO/PAPER (safe)"
    else
        info "EXECUTION_MODE is ${EXEC_MODE}"
    fi
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo "============================================================================"
echo -e " REHEARSAL SUMMARY"
echo "============================================================================"
echo -e "  ${GREEN}PASS:${NC} ${PASS}"
echo -e "  ${RED}FAIL:${NC} ${FAIL}"
echo -e "  ${YELLOW}WARN:${NC} ${WARN}"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}RESULT: ALL CHECKS PASSED${NC}"
    echo ""
    echo "  Next steps:"
    echo "    1. Complete DOCS/FIRST_LIVE_TRADE_CHECKLIST.md (34-point go/no-go)"
    echo "    2. Set EXECUTION_MODE=LIVE and LIVE_TRADING_CONFIRMED=TRUE"
    echo "    3. Restart the Docker stack"
    echo ""
    exit 0
else
    echo -e "  ${RED}RESULT: ${FAIL} CHECK(S) FAILED${NC}"
    echo ""
    echo "  Fix all failures before proceeding to live trading."
    echo ""
    exit 1
fi

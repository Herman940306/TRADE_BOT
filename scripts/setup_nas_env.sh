#!/bin/bash
# ============================================================================
# Autonomous Alpha - NAS Environment Setup Script
# ============================================================================
# 
# This script creates the .env file directly on your NAS.
# Run this ON THE NAS via SSH - secrets never leave the NAS.
#
# Usage:
#   chmod +x setup_nas_env.sh
#   ./setup_nas_env.sh
#
# ============================================================================

set -e

ENV_FILE="/volume2/docker/autonomous_alpha/.env"

echo "=============================================="
echo "  Autonomous Alpha - NAS Environment Setup"
echo "=============================================="
echo ""
echo "This will create/update: $ENV_FILE"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Generate a secure webhook secret automatically
GENERATED_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-f0-9' | fold -w 64 | head -n 1)

echo ""
echo "=== DATABASE ==="
read -p "PostgreSQL Password [sovereign_secret_2024]: " POSTGRES_PASSWORD
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-sovereign_secret_2024}

echo ""
echo "=== TRADINGVIEW WEBHOOK ==="
echo "Auto-generated secret: $GENERATED_SECRET"
read -p "Use this secret? (y/n) [y]: " USE_GENERATED
USE_GENERATED=${USE_GENERATED:-y}
if [ "$USE_GENERATED" = "y" ]; then
    WEBHOOK_SECRET=$GENERATED_SECRET
else
    read -p "Enter your own webhook secret (min 32 chars): " WEBHOOK_SECRET
fi

echo ""
echo "=== VALR EXCHANGE (leave blank to skip) ==="
read -p "VALR API Key: " VALR_API_KEY
read -p "VALR API Secret: " VALR_API_SECRET

echo ""
echo "=== OPENROUTER AI (leave blank to skip) ==="
read -p "OpenRouter API Key: " OPENROUTER_API_KEY

echo ""
echo "=== DISCORD NOTIFICATIONS ==="
read -p "Discord Webhook URL: " DISCORD_WEBHOOK_URL
read -p "Alert Level [WARNING]: " DISCORD_ALERT_LEVEL
DISCORD_ALERT_LEVEL=${DISCORD_ALERT_LEVEL:-WARNING}

echo ""
echo "=== EMAIL BRIDGE (leave blank to skip) ==="
read -p "Gmail Address: " EMAIL_USER
read -p "Gmail App Password: " EMAIL_PASS

echo ""
echo "Writing $ENV_FILE ..."

cat > "$ENV_FILE" << EOF
# ============================================================================
# Autonomous Alpha v1.5.0 - Production Environment
# Generated: $(date -Iseconds)
# ============================================================================

# DATABASE
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# TRADINGVIEW WEBHOOK AUTHENTICATION
WEBHOOK_SECRET=$WEBHOOK_SECRET

# VALR EXCHANGE
VALR_API_KEY=$VALR_API_KEY
VALR_API_SECRET=$VALR_API_SECRET

# OPENROUTER AI
OPENROUTER_API_KEY=$OPENROUTER_API_KEY

# BUDGETGUARD (Sprint 6)
BUDGETGUARD_JSON_PATH=/app/data/budget_reports/latest_audit.json
BUDGETGUARD_STRICT_MODE=false

# DISCORD COMMAND CENTER (Sprint 7)
DISCORD_WEBHOOK_URL=$DISCORD_WEBHOOK_URL
DISCORD_ALERT_LEVEL=$DISCORD_ALERT_LEVEL
DISCORD_RATE_LIMIT_SECONDS=5
DISCORD_NOTIFICATIONS_ENABLED=true

# EMAIL BRIDGE
EMAIL_USER=$EMAIL_USER
EMAIL_PASS=$EMAIL_PASS
EOF

# Secure the file
chmod 600 "$ENV_FILE"

echo ""
echo "=============================================="
echo "  .env created successfully!"
echo "=============================================="
echo ""
echo "IMPORTANT - Save this webhook secret for TradingView:"
echo ""
echo "  $WEBHOOK_SECRET"
echo ""
echo "Next steps:"
echo "  1. Restart containers: sudo docker-compose -f docker-compose.prod.yml up -d"
echo "  2. Check logs: sudo docker-compose -f docker-compose.prod.yml logs -f bot --tail=50"
echo ""

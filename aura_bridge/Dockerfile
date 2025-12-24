# ============================================================================
# Project Autonomous Alpha v1.4.0
# Aura MCP Bridge - Dockerfile
# ============================================================================
#
# Reliability Level: SOVEREIGN TIER (Mission-Critical)
# Purpose: MCP Server for AI assistant integration
#
# SOVEREIGN MANDATE:
#   - Read-only database access
#   - Prometheus metrics queries
#   - Natural language trade explanations
#
# ============================================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose MCP server port
EXPOSE 8086

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8086/health || exit 1

# Run the MCP server
CMD ["python", "server.py"]

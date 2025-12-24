#!/usr/bin/env python3
"""Find the chat/tool execution HTTP endpoint."""
import paramiko
import os

DOCKER = '/usr/local/bin/docker'

# Configuration (Sanitized - SEC-001)
GATEWAY_IP = os.getenv("GATEWAY_IP", "127.0.0.1")
GATEWAY_USER = os.getenv("GATEWAY_USER", "admin")
GATEWAY_PASSWORD = os.getenv("SOVEREIGN_GATEWAY_PASSWORD")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(GATEWAY_IP, username=GATEWAY_USER, password=GATEWAY_PASSWORD)

# Check llm_proxy_service for chat endpoints
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway cat /app/aura_ia_mcp/services/llm_proxy_service.py 2>/dev/null | head -150')
print("=== llm_proxy_service.py ===")
print(stdout.read().decode())

# List all routes in the app
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway grep -rn "router = APIRouter\\|@router\\|@app" /app/aura_ia_mcp --include="*.py" 2>/dev/null | head -40')
print("\n=== All routers and routes ===")
print(stdout.read().decode())

c.close()

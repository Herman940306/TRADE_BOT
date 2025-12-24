#!/usr/bin/env python3
"""List all registered tools in the gateway MCP server."""
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

# Check the ML plugin file
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway cat /app/src/mcp_server/plugins/ml_intelligence.py 2>/dev/null | head -150')
content = stdout.read().decode()
if content:
    print("=== ML Plugin (first 150 lines) ===")
    print(content)
else:
    # Try alternative location
    stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway find /app -name "ml_intelligence.py" 2>/dev/null')
    print("=== ML Plugin location ===")
    print(stdout.read().decode())

# Check gateway logs for ML plugin loading
stdin, stdout, stderr = c.exec_command(f'{DOCKER} logs aura_ia_gateway 2>&1 | grep -i "ml plugin\\|ml_handlers\\|Loaded ML" | tail -10')
print("\n=== Gateway logs (ML plugin) ===")
print(stdout.read().decode())

c.close()

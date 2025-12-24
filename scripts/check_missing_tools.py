#!/usr/bin/env python3
"""Check how to bridge chat_service tools to MCP server."""
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

# Check if ide_agents_mcp_server imports chat_service
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway grep -n "chat_service\\|ChatService" /app/src/mcp_server/ide_agents_mcp_server.py 2>/dev/null')
print("=== chat_service imports in ide_agents_mcp_server.py ===")
print(stdout.read().decode() or "NONE - tools are not bridged!")

# Count tools in chat_service
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway grep -c "self.register(" /app/src/mcp_server/services/chat_service.py 2>/dev/null')
print(f"\n=== Total tools in chat_service.py: {stdout.read().decode().strip()} ===")

# Check the main entry point
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway cat /app/src/mcp_server/__init__.py 2>/dev/null')
print("\n=== mcp_server/__init__.py ===")
print(stdout.read().decode())

c.close()

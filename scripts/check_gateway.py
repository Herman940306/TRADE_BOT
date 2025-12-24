#!/usr/bin/env python3
"""
Quick diagnostic script to check gateway container structure.
"""
import paramiko
import os

# Configuration (Sanitized - SEC-001)
GATEWAY_IP = os.getenv("GATEWAY_IP", "127.0.0.1")
GATEWAY_USER = os.getenv("GATEWAY_USER", "admin")
GATEWAY_PASSWORD = os.getenv("SOVEREIGN_GATEWAY_PASSWORD")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(GATEWAY_IP, username=GATEWAY_USER, password=GATEWAY_PASSWORD)

# Check Python files in gateway container
DOCKER = '/usr/local/bin/docker'

stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway find /app -name "*.py" -type f 2>/dev/null | head -30')
print("=== Python files in gateway container ===")
print(stdout.read().decode())
print(stderr.read().decode())

# Check the MCP server module
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway ls -la /app/mcp_server/ 2>/dev/null')
print("=== MCP Server directory ===")
print(stdout.read().decode())
print(stderr.read().decode())

# Find what method contains the dispatch logic (line 2631)
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway sed -n "2580,2640p" /app/src/mcp_server/ide_agents_mcp_server.py 2>/dev/null')
content = stdout.read().decode()
print("=== Code around dispatch logic (lines 2580-2640) ===")
print(content)

# Check the call_tool method and what it calls
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway sed -n "4005,4025p" /app/src/mcp_server/ide_agents_mcp_server.py 2>/dev/null')
content = stdout.read().decode()
print("\n=== call_tool method (lines 4005-4025) ===")
print(content)

c.close()

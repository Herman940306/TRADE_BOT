#!/usr/bin/env python3
"""
============================================================================
Project Autonomous Alpha v1.4.0
Gateway MCP Server Bug Fix
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: None
Side Effects: Patches ide_agents_mcp_server.py in aura_ia_gateway container

PURPOSE
-------
Fixes the missing _dispatch_tool_call method bug by changing the call_tool
method to use the correct method name: _call_tool

BUG DETAILS
-----------
- call_tool() calls self._dispatch_tool_call(name, arguments)
- But the actual method is named _call_tool(), not _dispatch_tool_call()
- This causes AttributeError when any tool is invoked

============================================================================
"""
import paramiko
import os

DOCKER = '/usr/local/bin/docker'
FILE_PATH = '/app/src/mcp_server/ide_agents_mcp_server.py'

# Configuration (Sanitized - SEC-001)
GATEWAY_IP = os.getenv("GATEWAY_IP", "127.0.0.1")
GATEWAY_USER = os.getenv("GATEWAY_USER", "admin")
GATEWAY_PASSWORD = os.getenv("SOVEREIGN_GATEWAY_PASSWORD")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(GATEWAY_IP, username=GATEWAY_USER, password=GATEWAY_PASSWORD)

# Create the sed command to fix the bug
# Replace _dispatch_tool_call with _call_tool in the call_tool method
sed_cmd = f"{DOCKER} exec aura_ia_gateway sed -i 's/_dispatch_tool_call/_call_tool/g' {FILE_PATH}"

print(f"Executing fix: {sed_cmd}")
stdin, stdout, stderr = c.exec_command(sed_cmd)
err = stderr.read().decode()
out = stdout.read().decode()

if err:
    print(f"Error: {err}")
else:
    print("Fix applied successfully!")

# Verify the fix
print("\n=== Verifying fix ===")
stdin, stdout, stderr = c.exec_command(f'{DOCKER} exec aura_ia_gateway grep -n "_dispatch_tool_call\\|_call_tool" {FILE_PATH} | head -10')
print(stdout.read().decode())

# Restart the container to apply changes
print("\n=== Restarting aura_ia_gateway container ===")
stdin, stdout, stderr = c.exec_command(f'{DOCKER} restart aura_ia_gateway')
print(stdout.read().decode())
print(stderr.read().decode())

c.close()
print("\nDone! Please toggle the aura-gateway MCP server in Kiro to reconnect.")

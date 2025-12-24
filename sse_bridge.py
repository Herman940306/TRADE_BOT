#!/usr/bin/env python3
"""
============================================================================
Project Autonomous Alpha v1.4.0
SSE Bridge - SSH Tunnel for MCP SSE Transport
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Stdio from Kiro IDE
Side Effects: SSH connection to NAS, HTTP proxy to Gateway SSE

PURPOSE
-------
This bridge proxies MCP SSE traffic through SSH to bypass Kiro's
localhost-only restriction for HTTP URLs. It connects to the Gateway's
SSE endpoint via the NAS and pipes the traffic through stdio.

============================================================================
"""

import paramiko
import sys
import os
import threading
import time
import json

# Configuration (Sanitized - SEC-001)
HOSTNAME = os.getenv("GATEWAY_IP", "127.0.0.1")
USERNAME = os.getenv("GATEWAY_USER", "admin")
PASSWORD = os.getenv("SOVEREIGN_GATEWAY_PASSWORD")

# Gateway SSE endpoint (internal to NAS network)
GATEWAY_URL = "http://localhost:9200"

# Global flag for clean shutdown
running = True


def pipe_stdin_to_channel(channel):
    """Pipe stdin to SSH channel."""
    global running
    try:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        
        while running:
            try:
                data = sys.stdin.buffer.read(1)
                if not data:
                    break
                channel.sendall(data)
            except (IOError, OSError):
                break
    except Exception:
        pass


def main():
    """
    Main entry point - creates SSH tunnel and proxies SSE.
    """
    global running
    
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=30)
        
        transport = client.get_transport()
        channel = transport.open_session()
        
        # Run a Python SSE client inside the NAS that talks to the Gateway
        # and pipes the MCP protocol through stdio
        remote_script = '''python3 -u -c "
import sys
import json
import urllib.request
import urllib.parse
import threading

GATEWAY_URL = 'http://localhost:9200'
session_id = None
messages_url = None

def read_sse():
    global session_id, messages_url
    req = urllib.request.Request(GATEWAY_URL + '/sse')
    req.add_header('Accept', 'text/event-stream')
    
    with urllib.request.urlopen(req) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                data = line[5:].strip()
                if event_type == 'endpoint':
                    messages_url = GATEWAY_URL + data
                elif event_type == 'message':
                    sys.stdout.write(data + chr(10))
                    sys.stdout.flush()

def send_messages():
    global messages_url
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        if messages_url:
            req = urllib.request.Request(
                messages_url,
                data=line.encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            try:
                urllib.request.urlopen(req)
            except Exception as e:
                sys.stderr.write(str(e) + chr(10))

t1 = threading.Thread(target=read_sse, daemon=True)
t2 = threading.Thread(target=send_messages, daemon=True)
t1.start()
t2.start()
t1.join()
"
'''
        channel.exec_command(remote_script)
        
        # Start stdin reader thread
        stdin_thread = threading.Thread(target=pipe_stdin_to_channel, args=(channel,))
        stdin_thread.start()
        
        # Main loop: read from channel, write to stdout
        try:
            while running:
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                
                if channel.recv_stderr_ready():
                    err = channel.recv_stderr(4096)
                    if err:
                        sys.stderr.buffer.write(err)
                        sys.stderr.buffer.flush()
                
                if channel.exit_status_ready():
                    while channel.recv_ready():
                        data = channel.recv(4096)
                        if data:
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                    break
                
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            running = False
            
    except Exception as e:
        sys.stderr.write(f"Bridge Error: {e}\n")
        sys.exit(1)
    finally:
        running = False
        try:
            client.close()
        except:
            pass
        os._exit(0)


if __name__ == "__main__":
    main()

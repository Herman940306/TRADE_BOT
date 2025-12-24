#!/usr/bin/env python3
"""
============================================================================
Project Autonomous Alpha v1.4.0
Gateway SSE-to-Stdio Proxy
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Stdio from SSH, SSE from Gateway
Side Effects: HTTP requests to Gateway

PURPOSE
-------
This proxy runs on the NAS and bridges the Gateway's SSE endpoint to stdio,
allowing Kiro to connect via SSH without port forwarding.

============================================================================
"""

import sys
import json
import threading
import time
import urllib.request
import urllib.error

GATEWAY_URL = "http://localhost:9200"
session_id = None
messages_url = None
running = True


def read_sse_stream():
    """Read SSE events from Gateway and write to stdout."""
    global session_id, messages_url, running
    
    try:
        req = urllib.request.Request(GATEWAY_URL + "/sse")
        req.add_header("Accept", "text/event-stream")
        req.add_header("Cache-Control", "no-cache")
        
        with urllib.request.urlopen(req, timeout=300) as response:
            event_type = None
            
            while running:
                line = response.readline()
                if not line:
                    break
                
                line = line.decode("utf-8").rstrip("\r\n")
                
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                    
                    if event_type == "endpoint":
                        # Extract session info from endpoint
                        messages_url = GATEWAY_URL + data
                        sys.stderr.write(f"SSE endpoint received: {messages_url}\n")
                        sys.stderr.flush()
                    elif event_type == "message":
                        # Forward MCP message to stdout
                        sys.stdout.write(data + "\n")
                        sys.stdout.flush()
                elif line.startswith(":"):
                    # Comment/ping, ignore
                    pass
                    
    except Exception as e:
        sys.stderr.write(f"SSE read error: {e}\n")
        sys.stderr.flush()
    finally:
        running = False


def read_stdin_and_post():
    """Read from stdin and POST to Gateway messages endpoint."""
    global messages_url, running
    
    # Wait for messages_url to be set
    while running and messages_url is None:
        time.sleep(0.1)
    
    if not running:
        return
    
    try:
        while running:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                req = urllib.request.Request(
                    messages_url,
                    data=line.encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    pass
            except urllib.error.HTTPError as e:
                sys.stderr.write(f"POST error {e.code}: {e.reason}\n")
                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"POST error: {e}\n")
                sys.stderr.flush()
                
    except Exception as e:
        sys.stderr.write(f"Stdin read error: {e}\n")
        sys.stderr.flush()
    finally:
        running = False


def main():
    global running
    
    sys.stderr.write("Gateway Stdio Proxy starting...\n")
    sys.stderr.write(f"Gateway URL: {GATEWAY_URL}\n")
    sys.stderr.flush()
    
    # Start SSE reader thread
    sse_thread = threading.Thread(target=read_sse_stream, daemon=True)
    sse_thread.start()
    
    # Start stdin reader thread
    stdin_thread = threading.Thread(target=read_stdin_and_post, daemon=True)
    stdin_thread.start()
    
    # Wait for either thread to finish
    try:
        while running and sse_thread.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        running = False


if __name__ == "__main__":
    main()

"""
============================================================================
Project Autonomous Alpha v1.3.2
Email-to-Webhook Bridge - TradingView Alert Ingestion
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Gmail IMAP with App Password
Side Effects: Reads emails, forwards to bot webhook

SOVEREIGN MANDATE:
- Bypass TradingView Free Tier webhook limitation
- Poll Gmail for alert emails from TradingView
- Extract JSON payload and forward to bot container
- Robust error handling with unique error codes

============================================================================
"""

import imaplib
import email
import requests
import time
import json
import os
import sys
import re
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional, Dict, Any


# ============================================================================
# CONFIGURATION
# ============================================================================

EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
BOT_URL = os.getenv("BOT_URL", "http://bot:8080/webhook/tradingview")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
TRADINGVIEW_SENDER = os.getenv("TRADINGVIEW_SENDER", "noreply@tradingview.com")


# ============================================================================
# LOGGING UTILITIES
# ============================================================================

def log_info(message: str) -> None:
    """
    Log informational message with timestamp.
    
    Reliability Level: STANDARD
    Input Constraints: Non-empty string
    Side Effects: Writes to stdout
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] INFO: {message}", flush=True)


def log_error(code: str, message: str) -> None:
    """
    Log error message with unique error code.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Error code format BRIDGE-XXX
    Side Effects: Writes to stderr
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] ERROR [{code}]: {message}", file=sys.stderr, flush=True)


def log_signal(action: str, symbol: str, details: str = "") -> None:
    """
    Log trading signal detection.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid action and symbol
    Side Effects: Writes to stdout
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] 🚀 SIGNAL: {action} {symbol} {details}", flush=True)


# ============================================================================
# EMAIL PROCESSING
# ============================================================================

def extract_json_from_body(body: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON payload from email body text.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Email body as string
    Side Effects: None
    
    Returns:
        Dict containing parsed JSON or None if extraction fails
        
    Handles multiple JSON formats:
    - Raw JSON in body
    - JSON embedded in HTML
    - JSON with surrounding text
    """
    if not body:
        return None
    
    # Clean up the body text
    body = body.strip()
    
    # Try to find JSON object pattern
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, body, re.DOTALL)
    
    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    
    # Fallback: try finding JSON between first { and last }
    try:
        start = body.find('{')
        end = body.rfind('}') + 1
        if start != -1 and end > start:
            json_str = body[start:end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    return None


def get_email_body(msg: email.message.Message) -> str:
    """
    Extract plain text body from email message.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid email.message.Message object
    Side Effects: None
    
    Returns:
        Plain text body content
    """
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            # Prefer plain text
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='replace')
                        break
                except Exception:
                    continue
            
            # Fallback to HTML if no plain text
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        html_body = payload.decode(charset, errors='replace')
                        # Strip HTML tags for JSON extraction
                        body = re.sub(r'<[^>]+>', ' ', html_body)
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='replace')
        except Exception:
            pass
    
    return body


def forward_to_bot(json_data: Dict[str, Any]) -> bool:
    """
    Forward extracted JSON payload to bot webhook.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid JSON dict with trading signal
    Side Effects: HTTP POST to bot container
    
    Returns:
        True if successfully forwarded, False otherwise
    """
    try:
        response = requests.post(
            BOT_URL,
            json=json_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            log_info(f"📡 Bot accepted signal: HTTP {response.status_code}")
            return True
        else:
            log_error("BRIDGE-003", f"Bot rejected signal: HTTP {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        log_error("BRIDGE-004", f"Cannot connect to bot at {BOT_URL}")
        return False
    except requests.exceptions.Timeout:
        log_error("BRIDGE-005", "Bot request timed out after 30s")
        return False
    except Exception as e:
        log_error("BRIDGE-006", f"Unexpected error forwarding to bot: {e}")
        return False


# ============================================================================
# IMAP CONNECTION
# ============================================================================

def check_emails() -> int:
    """
    Check Gmail inbox for unread TradingView alerts.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid EMAIL_USER and EMAIL_PASS
    Side Effects: Reads and marks emails as read, forwards to bot
    
    Returns:
        Number of signals processed
    """
    signals_processed = 0
    mail = None
    
    try:
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("INBOX")
        
        # Search for unread emails from TradingView
        search_criteria = f'(UNSEEN FROM "{TRADINGVIEW_SENDER}")'
        status, messages = mail.search(None, search_criteria)
        
        if status != "OK":
            log_error("BRIDGE-007", f"IMAP search failed: {status}")
            return 0
        
        message_ids = messages[0].split()
        
        if not message_ids:
            return 0
        
        log_info(f"📬 Found {len(message_ids)} unread TradingView email(s)")
        
        for msg_id in message_ids:
            try:
                # Fetch the email
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                
                if status != "OK":
                    log_error("BRIDGE-008", f"Failed to fetch email {msg_id}")
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Get subject for logging
                        subject = decode_header(msg["Subject"])[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(errors='replace')
                        
                        log_info(f"📧 Processing: {subject}")
                        
                        # Extract body and JSON
                        body = get_email_body(msg)
                        json_data = extract_json_from_body(body)
                        
                        if json_data:
                            # Log the signal
                            symbol = json_data.get("symbol", "UNKNOWN")
                            action = json_data.get("action", json_data.get("side", "UNKNOWN"))
                            log_signal(action, symbol)
                            
                            # Forward to bot
                            if forward_to_bot(json_data):
                                signals_processed += 1
                        else:
                            log_error("BRIDGE-009", f"No valid JSON found in email: {subject}")
                            log_info(f"Email body preview: {body[:200]}...")
                
            except Exception as e:
                log_error("BRIDGE-010", f"Error processing email {msg_id}: {e}")
                continue
        
    except imaplib.IMAP4.error as e:
        log_error("BRIDGE-001", f"IMAP authentication failed: {e}")
    except Exception as e:
        log_error("BRIDGE-002", f"Email check failed: {e}")
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
    
    return signals_processed


# ============================================================================
# MAIN LOOP
# ============================================================================

def validate_config() -> bool:
    """
    Validate required configuration before starting.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Logs errors for missing config
    
    Returns:
        True if config is valid, False otherwise
    """
    valid = True
    
    if not EMAIL_USER:
        log_error("BRIDGE-100", "EMAIL_USER environment variable not set")
        valid = False
    
    if not EMAIL_PASS:
        log_error("BRIDGE-101", "EMAIL_PASS environment variable not set")
        valid = False
    
    return valid


def main() -> None:
    """
    Main entry point for Email-to-Webhook Bridge.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid environment configuration
    Side Effects: Continuous polling loop
    """
    print("=" * 60, flush=True)
    print("AUTONOMOUS ALPHA v1.3.2 - EMAIL-TO-WEBHOOK BRIDGE", flush=True)
    print("=" * 60, flush=True)
    print(f"IMAP Server: {IMAP_SERVER}:{IMAP_PORT}", flush=True)
    print(f"Bot URL: {BOT_URL}", flush=True)
    print(f"Poll Interval: {POLL_INTERVAL}s", flush=True)
    print(f"Watching for: {TRADINGVIEW_SENDER}", flush=True)
    print("=" * 60, flush=True)
    
    if not validate_config():
        log_error("BRIDGE-999", "Configuration validation failed. Exiting.")
        sys.exit(1)
    
    log_info("🕯️ Sovereign Bridge Active. Waiting for TradingView signals...")
    
    # Track statistics
    total_signals = 0
    check_count = 0
    
    while True:
        try:
            check_count += 1
            signals = check_emails()
            total_signals += signals
            
            if signals > 0:
                log_info(f"📊 Session stats: {total_signals} total signals processed")
            
        except KeyboardInterrupt:
            log_info("🛑 Bridge shutdown requested")
            break
        except Exception as e:
            log_error("BRIDGE-500", f"Unexpected error in main loop: {e}")
        
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

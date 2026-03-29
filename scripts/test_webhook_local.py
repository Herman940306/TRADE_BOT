from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get('APP_URL', 'http://localhost:8080')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'local_dev_webhook_secret_minimum_32_chars_replace_me')
OPERATOR_ID = os.environ.get('HITL_OPERATOR', 'local_operator')
